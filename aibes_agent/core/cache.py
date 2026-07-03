"""Tool result cache with in-memory and persistent backends."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from aibes_agent.tools.base import ToolResult


@dataclass
class _CachedEntry:
    result: ToolResult
    expires_at: float


class ToolResultCache(ABC):
    """Abstract tool result cache with TTL support."""

    def __init__(self, default_ttl: float = 60.0) -> None:
        self.default_ttl = default_ttl

    @staticmethod
    def make_key(tool_name: str, args: Dict[str, Any], cwd: str) -> str:
        """Generate a cache key from tool name, arguments, and working directory."""
        data = {"tool": tool_name, "args": args, "cwd": cwd}
        normalized = json.dumps(data, sort_keys=True, ensure_ascii=True)
        return hashlib.md5(normalized.encode("utf-8")).hexdigest()

    @abstractmethod
    def get(self, key: str) -> Optional[ToolResult]: ...

    @abstractmethod
    def set(
        self,
        key: str,
        result: ToolResult,
        ttl: Optional[float] = None,
    ) -> None: ...

    @abstractmethod
    def clear(self) -> None: ...


class MemoryToolResultCache(ToolResultCache):
    """In-memory TTL cache for tool results."""

    def __init__(self, default_ttl: float = 60.0) -> None:
        super().__init__(default_ttl)
        self._store: Dict[str, _CachedEntry] = {}

    def get(self, key: str) -> Optional[ToolResult]:
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.monotonic() > entry.expires_at:
            del self._store[key]
            return None
        return entry.result

    def set(
        self,
        key: str,
        result: ToolResult,
        ttl: Optional[float] = None,
    ) -> None:
        ttl = ttl if ttl is not None else self.default_ttl
        self._store[key] = _CachedEntry(
            result=result,
            expires_at=time.monotonic() + ttl,
        )

    def clear(self) -> None:
        self._store.clear()


class SqliteToolResultCache(ToolResultCache):
    """SQLite-backed persistent cache for tool results."""

    _SCHEMA = """
    CREATE TABLE IF NOT EXISTS tool_cache (
        key TEXT PRIMARY KEY,
        success INTEGER NOT NULL,
        content TEXT NOT NULL,
        error TEXT,
        metadata TEXT NOT NULL,
        created_at REAL NOT NULL,
        expires_at REAL NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_tool_cache_expires ON tool_cache(expires_at);
    """

    def __init__(
        self,
        path: str = ".aibes-agent/cache.db",
        default_ttl: float = 60.0,
        max_size: int = 10000,
    ) -> None:
        super().__init__(default_ttl)
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_size = max_size
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(str(self.path)) as conn:
            conn.executescript(self._SCHEMA)

    def _result_to_row(self, result: ToolResult) -> tuple:
        return (
            1 if result.success else 0,
            result.content,
            result.error or "",
            json.dumps(result.metadata, ensure_ascii=False),
        )

    def _row_to_result(self, row: tuple) -> ToolResult:
        success, content, error, metadata = row
        return ToolResult(
            success=bool(success),
            content=content,
            error=error or None,
            metadata=json.loads(metadata),
        )

    def get(self, key: str) -> Optional[ToolResult]:
        with sqlite3.connect(str(self.path)) as conn:
            cur = conn.execute(
                "SELECT success, content, error, metadata FROM tool_cache "
                "WHERE key = ? AND expires_at > ?",
                (key, time.time()),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return self._row_to_result(row)

    def set(
        self,
        key: str,
        result: ToolResult,
        ttl: Optional[float] = None,
    ) -> None:
        ttl = ttl if ttl is not None else self.default_ttl
        expires_at = time.time() + ttl
        created_at = time.time()
        row = self._result_to_row(result)
        with sqlite3.connect(str(self.path)) as conn:
            conn.execute(
                "INSERT INTO tool_cache(key, success, content, error, metadata, created_at, expires_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET success=excluded.success, content=excluded.content, "
                "error=excluded.error, metadata=excluded.metadata, created_at=excluded.created_at, "
                "expires_at=excluded.expires_at",
                (key, *row, created_at, expires_at),
            )
            conn.execute("DELETE FROM tool_cache WHERE expires_at <= ?", (created_at,))
            if self.max_size > 0:
                conn.execute(
                    "DELETE FROM tool_cache WHERE key NOT IN "
                    "(SELECT key FROM tool_cache ORDER BY created_at DESC LIMIT ?)",
                    (self.max_size,),
                )
            conn.commit()

    def clear(self) -> None:
        with sqlite3.connect(str(self.path)) as conn:
            conn.execute("DELETE FROM tool_cache")
            conn.commit()
