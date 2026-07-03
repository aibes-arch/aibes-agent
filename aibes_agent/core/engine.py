from __future__ import annotations

import json
from typing import Any, AsyncIterator, Dict, List, Optional

from loguru import logger

from aibes_agent.core.cache import MemoryToolResultCache
from aibes_agent.core.context import ContextWindow, Message
from aibes_agent.core.summarizer import SessionSummarizer
from aibes_agent.core.llm import LLMClient
from aibes_agent.core.router import ModelRouter
from aibes_agent.core.session import (
    SessionStore,
    context_from_session,
    session_from_context,
)
from aibes_agent.core.stats import RunStats
from aibes_agent.core.tool_registry import ToolRegistry
from aibes_agent.permissions.engine import PermissionEngine
from aibes_agent.tools.base import ToolContext


class AgentConfig:
    """Agent 配置。"""

    def __init__(
        self,
        system_prompt: str = "",
        max_turns: int = 30,
        max_tokens_per_turn: int = 4000,
        temperature: float = 0.2,
        auto_compact: bool = True,
    ):
        self.system_prompt = system_prompt
        self.max_turns = max_turns
        self.max_tokens_per_turn = max_tokens_per_turn
        self.temperature = temperature
        self.auto_compact = auto_compact


class AgentLoop:
    """Agent 主循环。"""

    def __init__(
        self,
        llm: LLMClient,
        registry: ToolRegistry,
        config: AgentConfig,
        permission_engine: Optional[PermissionEngine] = None,
        tool_context: Optional[ToolContext] = None,
        model_router: Optional[ModelRouter] = None,
        session_store: Optional[SessionStore] = None,
        summarizer: Optional[SessionSummarizer] = None,
    ):
        self.llm = llm
        self.registry = registry
        self.config = config
        self.permission_engine = permission_engine or PermissionEngine()
        self.tool_context = tool_context or ToolContext(cwd="/")
        if self.tool_context.cache is None:
            self.tool_context.cache = MemoryToolResultCache()
        self.model_router = model_router
        self.session_store = session_store
        self.summarizer = summarizer
        self.stats = RunStats()

    async def run(
        self,
        task: str,
        session_id: Optional[str] = None,
        initial_context: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """运行 Agent 循环，产生事件。"""
        ctx = await self._prepare_context(task, session_id)

        if initial_context:
            self.tool_context.metadata.update(initial_context)

        yield {"type": "user_task", "content": task}

        for turn in range(self.config.max_turns):
            self.stats.turn_count = turn + 1

            if self.config.auto_compact and ctx.should_compact():
                await ctx.compact(self.llm)
                yield {"type": "compact", "message": "Context compacted"}

            tools = self.registry.to_openai_schemas()
            effective_llm = self._choose_llm(task)

            logger.info(
                "Turn {}/{}: calling LLM (model={})...",
                turn + 1,
                self.config.max_turns,
                effective_llm.model,
            )

            try:
                response = await effective_llm.chat(
                    messages=ctx.to_openai_messages(),
                    tools=tools,
                    max_tokens=self.config.max_tokens_per_turn,
                    temperature=self.config.temperature,
                )
            except Exception as exc:
                error_msg = f"LLM request failed: {exc}"
                logger.error(error_msg)
                self.stats.add_error(error_msg)
                await self._persist_session(session_id, ctx)
                yield {"type": "error", "message": error_msg, "stats": self.stats.to_dict()}
                return

            self.stats.llm_call_count += 1
            self.stats.update_from_usage(response.usage)

            yield {
                "type": "llm_response",
                "turn": turn + 1,
                "content": response.content,
                "tool_calls": response.tool_calls,
                "model": response.model or effective_llm.model,
                "usage": response.usage,
            }

            logger.info(
                "LLM responded (model={}): content_chars={} tool_calls={}",
                response.model or effective_llm.model,
                len(response.content or ""),
                len(response.tool_calls),
            )
            ctx.add_assistant(response.content, response.tool_calls)

            if not response.has_tool_calls():
                await self._persist_session(session_id, ctx)
                yield {
                    "type": "final",
                    "content": response.content,
                    "stats": self.stats.to_dict(),
                }
                return

            # 权限检查
            allowed_tool_calls = []
            for tc in response.tool_calls:
                tool_name = tc["function"]["name"]
                arguments = tc["function"].get("arguments", {})
                if isinstance(arguments, str):
                    arguments = json.loads(arguments)
                try:
                    permitted = await self.permission_engine.check(
                        tool_name, arguments, self.tool_context
                    )
                except Exception as exc:
                    permitted = False
                    logger.warning("Permission check failed for {}: {}", tool_name, exc)

                if permitted:
                    allowed_tool_calls.append(tc)
                else:
                    self.stats.add_error(f"Permission denied: {tool_name}")
                    yield {
                        "type": "permission_denied",
                        "tool_call": tc,
                        "reason": "Permission denied",
                    }
                    ctx.add_tool_result(
                        tc["id"],
                        f"Permission denied: tool '{tool_name}' was not allowed.",
                        tool_name,
                    )

            if not allowed_tool_calls:
                error_msg = "All tool calls were denied"
                self.stats.add_error(error_msg)
                await self._persist_session(session_id, ctx)
                yield {"type": "error", "message": error_msg, "stats": self.stats.to_dict()}
                return

            # 执行工具
            logger.info("Executing {} tool call(s)...", len(allowed_tool_calls))
            try:
                tool_results = await self.registry.execute(allowed_tool_calls, self.tool_context)
            except Exception as exc:
                error_msg = f"Tool execution failed: {exc}"
                logger.error(error_msg)
                self.stats.add_error(error_msg)
                await self._persist_session(session_id, ctx)
                yield {"type": "error", "message": error_msg, "stats": self.stats.to_dict()}
                return

            self.stats.tool_call_count += len(tool_results)

            for tr in tool_results:
                yield {
                    "type": "tool_result",
                    "tool_call_id": tr["tool_call_id"],
                    "name": tr["name"],
                    "content": tr["content"],
                }
                ctx.add_tool_result(tr["tool_call_id"], tr["content"], tr["name"])

            yield {"type": "stats", "data": self.stats.to_dict()}

        error_msg = f"Reached max turns ({self.config.max_turns})"
        self.stats.add_error(error_msg)
        await self._persist_session(session_id, ctx)
        yield {"type": "error", "message": error_msg, "stats": self.stats.to_dict()}

    async def _prepare_context(self, task: str, session_id: Optional[str]) -> ContextWindow:
        """Restore context from a session or create a fresh one."""
        if session_id and self.session_store:
            state = await self.session_store.load(session_id)
            if state is not None:
                ctx = context_from_session(state)
                if self.summarizer is not None and len(state.messages) > 6:
                    summary = await self.summarizer.summarize(state)
                    if summary:
                        self.tool_context.metadata["session_summary"] = summary
                ctx.add_user(task)
                return ctx

        ctx = ContextWindow()
        if self.config.system_prompt:
            ctx.add(Message(role="system", content=self.config.system_prompt))
        ctx.add_user(task)
        return ctx

    def _choose_llm(self, task: str) -> LLMClient:
        """Pick the right LLM client based on the model router."""
        if self.model_router is None:
            return self.llm
        model = self.model_router.route(task)
        if model is None:
            return self.llm
        return self.llm.with_model(model)

    async def _persist_session(self, session_id: Optional[str], ctx: ContextWindow) -> None:
        """Persist conversation state if a session store is configured."""
        if not session_id or not self.session_store:
            return
        tasks = self.tool_context.metadata.get("tasks_v2", [])
        state = session_from_context(session_id, ctx, tasks)
        await self.session_store.save(state)
