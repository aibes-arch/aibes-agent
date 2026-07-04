"""Web runner: bridge AgentLoop event streams to per-session SSE queues."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional

from aibes_agent.core.engine import AgentConfig, AgentLoop
from aibes_agent.core.llm import LLMClient
from aibes_agent.core.router import ModelRouter
from aibes_agent.core.session import SessionStore
from aibes_agent.core.tool_registry import ToolRegistry
from aibes_agent.permissions.engine import PermissionEngine
from aibes_agent.tools.base import ToolContext


@dataclass
class WebSession:
    """State for a single browser/session connection."""

    session_id: str
    queues: List[asyncio.Queue] = field(default_factory=list)
    task_queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    running: bool = False


class WebRunner:
    """Manage multiple web sessions and run agents on demand."""

    def __init__(
        self,
        registry: ToolRegistry,
        agent_config: AgentConfig,
        llm: LLMClient,
        permission_engine: PermissionEngine,
        model_router: Optional[ModelRouter],
        session_store: SessionStore,
        tool_context: ToolContext,
    ) -> None:
        self.registry = registry
        self.agent_config = agent_config
        self.llm = llm
        self.permission_engine = permission_engine
        self.model_router = model_router
        self.session_store = session_store
        self.tool_context = tool_context
        self._sessions: Dict[str, WebSession] = {}

    def subscribe(self, session_id: str) -> asyncio.Queue:
        """Register a new SSE consumer for ``session_id``."""
        session = self._get_or_create(session_id)
        queue: asyncio.Queue = asyncio.Queue()
        session.queues.append(queue)
        return queue

    def unsubscribe(self, session_id: str, queue: asyncio.Queue) -> None:
        session = self._sessions.get(session_id)
        if session and queue in session.queues:
            session.queues.remove(queue)

    async def submit(self, session_id: str, task: str) -> None:
        """Queue an agent task for ``session_id``.

        Tasks for the same session are executed sequentially so that they share
        a consistent conversation context. New tasks can be submitted while
        another task is already running.
        """
        session = self._get_or_create(session_id)
        await session.task_queue.put(task)
        if not session.running:
            session.running = True
            asyncio.create_task(self._worker(session_id))

    async def event_stream(self, session_id: str) -> AsyncIterator[Dict[str, Any]]:
        """Async generator yielding SSE payloads for a session.

        The stream stays open across multiple queued tasks. ``None`` is used
        internally as a task-boundary marker and is not forwarded to clients.
        """
        queue = self.subscribe(session_id)
        try:
            while True:
                event = await queue.get()
                if event is None:
                    # Task boundary marker; keep stream alive for next task.
                    continue
                yield {"data": json.dumps(event, ensure_ascii=False)}
        finally:
            self.unsubscribe(session_id, queue)

    def _get_or_create(self, session_id: str) -> WebSession:
        if session_id not in self._sessions:
            self._sessions[session_id] = WebSession(session_id=session_id)
        return self._sessions[session_id]

    async def _worker(self, session_id: str) -> None:
        """Process queued tasks for ``session_id`` one at a time."""
        session = self._sessions.get(session_id)
        if session is None:
            return
        try:
            while True:
                try:
                    task = session.task_queue.get_nowait()
                except asyncio.QueueEmpty:
                    session.running = False
                    return
                await self._run_task(session_id, task)
        except Exception:
            session.running = False
            raise

    async def _run_task(self, session_id: str, task: str) -> None:
        """Run a single agent task and broadcast events to subscribers."""
        agent = AgentLoop(
            llm=self.llm,
            registry=self.registry,
            config=self.agent_config,
            permission_engine=self.permission_engine,
            tool_context=self.tool_context,
            model_router=self.model_router,
            session_store=self.session_store,
        )
        try:
            async for event in agent.run(task, session_id=session_id):
                await self._broadcast(session_id, event)
        except Exception as exc:
            await self._broadcast(
                session_id,
                {"type": "error", "message": f"Agent run failed: {exc}"},
            )
        finally:
            await self._broadcast(session_id, None)

    async def _broadcast(self, session_id: str, event: Optional[Dict[str, Any]]) -> None:
        session = self._sessions.get(session_id)
        if session is None:
            return
        for queue in list(session.queues):
            await queue.put(event)
