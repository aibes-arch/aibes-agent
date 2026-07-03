"""Session persistence: save and restore conversation state."""

from __future__ import annotations

import json
import sqlite3
import time
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

    @abstractmethod
    async def delete(self, session_id: str) -> bool:
        """Delete a single session. Return True if it existed."""
        ...

    @abstractmethod
    async def clear(self) -> None:
        """Delete all sessions."""
        ...

    @abstractmethod
    async def cleanup(self, max_age_seconds: float) -> int:
        """Delete sessions older than *max_age_seconds*. Return deleted count."""
        ...


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
            "updated_at": time.time(),
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

    async def delete(self, session_id: str) -> bool:
        path = self._path(session_id)
        if not path.exists():
            return False
        path.unlink()
        return True

    async def clear(self) -> None:
        for path in self.directory.glob("*.json"):
            path.unlink()

    async def cleanup(self, max_age_seconds: float) -> int:
        cutoff = time.time() - max_age_seconds
        deleted = 0
        for path in self.directory.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if data.get("updated_at", 0) < cutoff:
                    path.unlink()
                    deleted += 1
            except Exception:
                continue
        return deleted


class MemorySessionStore(SessionStore):
    """In-memory session store. Data is lost when the process exits."""

    def __init__(self) -> None:
        self._store: Dict[str, SessionState] = {}
        self._updated_at: Dict[str, float] = {}

    async def save(self, state: SessionState) -> None:
        self._store[state.session_id] = SessionState(
            session_id=state.session_id,
            messages=list(state.messages),
            tasks=list(state.tasks),
            metadata=dict(state.metadata),
        )
        self._updated_at[state.session_id] = time.time()

    async def load(self, session_id: str) -> Optional[SessionState]:
        state = self._store.get(session_id)
        if state is None:
            return None
        return SessionState(
            session_id=state.session_id,
            messages=list(state.messages),
            tasks=list(state.tasks),
            metadata=dict(state.metadata),
        )

    async def list_sessions(self) -> List[str]:
        return sorted(self._store.keys())

    async def delete(self, session_id: str) -> bool:
        if session_id not in self._store:
            return False
        del self._store[session_id]
        self._updated_at.pop(session_id, None)
        return True

    async def clear(self) -> None:
        self._store.clear()
        self._updated_at.clear()

    async def cleanup(self, max_age_seconds: float) -> int:
        cutoff = time.time() - max_age_seconds
        expired = [sid for sid, ts in self._updated_at.items() if ts < cutoff]
        for sid in expired:
            self._store.pop(sid, None)
            self._updated_at.pop(sid, None)
        return len(expired)


class SQLiteSessionStore(SessionStore):
    """SQLite-backed session store."""

    _SCHEMA = """
    CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        data TEXT NOT NULL,
        updated_at REAL NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_sessions_updated_at ON sessions(updated_at);
    """

    def __init__(self, path: str = ".aibes-agent/sessions.db") -> None:
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock: Any = None
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(str(self.path)) as conn:
            conn.executescript(self._SCHEMA)

    async def _get_lock(self) -> Any:
        if self._lock is None:
            import asyncio

            self._lock = asyncio.Lock()
        return self._lock

    async def save(self, state: SessionState) -> None:
        import asyncio

        payload = {
            "session_id": state.session_id,
            "messages": state.messages,
            "tasks": state.tasks,
            "metadata": state.metadata,
        }
        data = json.dumps(payload, ensure_ascii=False)
        updated_at = time.time()
        async with await self._get_lock():
            await asyncio.to_thread(self._execute_save, state.session_id, data, updated_at)

    def _execute_save(self, session_id: str, data: str, updated_at: float) -> None:
        with sqlite3.connect(str(self.path)) as conn:
            conn.execute(
                "INSERT INTO sessions(session_id, data, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(session_id) DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at",
                (session_id, data, updated_at),
            )
            conn.commit()

    async def load(self, session_id: str) -> Optional[SessionState]:
        import asyncio

        async with await self._get_lock():
            row = await asyncio.to_thread(self._execute_load, session_id)
        if row is None:
            return None
        data = json.loads(row[0])
        return SessionState(
            session_id=data["session_id"],
            messages=data.get("messages", []),
            tasks=data.get("tasks", []),
            metadata=data.get("metadata", {}),
        )

    def _execute_load(self, session_id: str) -> Optional[tuple]:
        with sqlite3.connect(str(self.path)) as conn:
            cur = conn.execute("SELECT data FROM sessions WHERE session_id = ?", (session_id,))
            return cur.fetchone()

    async def list_sessions(self) -> List[str]:
        import asyncio

        async with await self._get_lock():
            rows = await asyncio.to_thread(self._execute_list)
        return sorted(row[0] for row in rows)

    def _execute_list(self) -> List[tuple]:
        with sqlite3.connect(str(self.path)) as conn:
            cur = conn.execute("SELECT session_id FROM sessions ORDER BY session_id")
            return cur.fetchall()

    async def delete(self, session_id: str) -> bool:
        import asyncio

        async with await self._get_lock():
            changed = await asyncio.to_thread(self._execute_delete, session_id)
        return changed > 0

    def _execute_delete(self, session_id: str) -> int:
        with sqlite3.connect(str(self.path)) as conn:
            cur = conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            conn.commit()
            return cur.rowcount

    async def clear(self) -> None:
        import asyncio

        async with await self._get_lock():
            await asyncio.to_thread(self._execute_clear)

    def _execute_clear(self) -> None:
        with sqlite3.connect(str(self.path)) as conn:
            conn.execute("DELETE FROM sessions")
            conn.commit()

    async def cleanup(self, max_age_seconds: float) -> int:
        import asyncio

        cutoff = time.time() - max_age_seconds
        async with await self._get_lock():
            deleted = await asyncio.to_thread(self._execute_cleanup, cutoff)
        return deleted

    def _execute_cleanup(self, cutoff: float) -> int:
        with sqlite3.connect(str(self.path)) as conn:
            cur = conn.execute("DELETE FROM sessions WHERE updated_at < ?", (cutoff,))
            conn.commit()
            return cur.rowcount


class RedisSessionStore(SessionStore):
    """Redis-backed session store (requires the ``redis`` package)."""

    def __init__(self, url: str = "redis://localhost:6379/0", ttl: float = 0.0) -> None:
        try:
            import redis.asyncio as aioredis  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "Redis session store requires 'redis'. Install with: pip install aibes-agent[redis]"
            ) from exc

        self._client = aioredis.from_url(url)
        self._ttl = int(ttl) if ttl > 0 else None

    def _key(self, session_id: str) -> str:
        return f"aibes:session:{session_id}"

    async def save(self, state: SessionState) -> None:
        payload = {
            "session_id": state.session_id,
            "messages": state.messages,
            "tasks": state.tasks,
            "metadata": state.metadata,
            "updated_at": time.time(),
        }
        await self._client.set(
            self._key(state.session_id),
            json.dumps(payload, ensure_ascii=False),
            ex=self._ttl,
        )

    async def load(self, session_id: str) -> Optional[SessionState]:
        raw = await self._client.get(self._key(session_id))
        if raw is None:
            return None
        data = json.loads(raw)
        return SessionState(
            session_id=data["session_id"],
            messages=data.get("messages", []),
            tasks=data.get("tasks", []),
            metadata=data.get("metadata", {}),
        )

    async def list_sessions(self) -> List[str]:
        keys = await self._client.keys("aibes:session:*")
        return sorted(key.decode().split(":", 2)[-1] for key in keys)

    async def delete(self, session_id: str) -> bool:
        return await self._client.delete(self._key(session_id)) > 0

    async def clear(self) -> None:
        keys = await self._client.keys("aibes:session:*")
        if keys:
            await self._client.delete(*keys)

    async def cleanup(self, max_age_seconds: float) -> int:
        cutoff = time.time() - max_age_seconds
        keys = await self._client.keys("aibes:session:*")
        deleted = 0
        for key in keys:
            raw = await self._client.get(key)
            if raw is None:
                continue
            try:
                data = json.loads(raw)
                if data.get("updated_at", 0) < cutoff:
                    await self._client.delete(key)
                    deleted += 1
            except Exception:
                continue
        return deleted


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
