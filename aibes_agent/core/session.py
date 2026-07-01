"""Session persistence: save and restore conversation state."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from aibes_agent.core.context import ContextWindow, Message


@dataclass
class SessionState:
    """Serializable agent state for a single session."""

    session_id: str
    messages: List[Dict[str, Any]] = field(default_factory=list)
    tasks: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class SessionStore(ABC):
    """Abstract session store."""

    @abstractmethod
    async def save(self, state: SessionState) -> None: ...

    @abstractmethod
    async def load(self, session_id: str) -> Optional[SessionState]: ...

    @abstractmethod
    async def list_sessions(self) -> List[str]: ...


class FileSessionStore(SessionStore):
    """File-based JSON session store."""

    def __init__(self, directory: str = ".aibes-agent/sessions") -> None:
        self.directory = Path(directory).expanduser()
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, session_id: str) -> Path:
        safe_id = Path(session_id).name
        return self.directory / f"{safe_id}.json"

    async def save(self, state: SessionState) -> None:
        path = self._path(state.session_id)
        payload = {
            "session_id": state.session_id,
            "messages": state.messages,
            "tasks": state.tasks,
            "metadata": state.metadata,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    async def load(self, session_id: str) -> Optional[SessionState]:
        path = self._path(session_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return SessionState(
            session_id=data["session_id"],
            messages=data.get("messages", []),
            tasks=data.get("tasks", []),
            metadata=data.get("metadata", {}),
        )

    async def list_sessions(self) -> List[str]:
        sessions = []
        for path in self.directory.glob("*.json"):
            sessions.append(path.stem)
        return sorted(sessions)


def context_from_session(state: SessionState) -> ContextWindow:
    """Rebuild a ContextWindow from a saved session state."""
    ctx = ContextWindow()
    for raw in state.messages:
        ctx.add(Message(**raw))
    return ctx


def session_from_context(
    session_id: str, ctx: ContextWindow, tasks: Optional[List[Any]] = None
) -> SessionState:
    """Create a SessionState from a ContextWindow."""
    return SessionState(
        session_id=session_id,
        messages=[m.model_dump() for m in ctx.messages],
        tasks=[t if isinstance(t, dict) else _task_to_dict(t) for t in (tasks or [])],
    )


def _task_to_dict(task: Any) -> Dict[str, Any]:
    if hasattr(task, "__dict__"):
        return task.__dict__
    return {"value": str(task)}
