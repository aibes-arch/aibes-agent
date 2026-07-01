"""工具结果缓存。"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from aibes_agent.tools.base import ToolResult


@dataclass
class _CachedEntry:
    result: "ToolResult"
    expires_at: float


class ToolResultCache:
    """基于内存的工具结果缓存，支持 TTL。"""

    def __init__(self, default_ttl: float = 60.0) -> None:
        self.default_ttl = default_ttl
        self._store: Dict[str, _CachedEntry] = {}

    def make_key(self, tool_name: str, args: Dict[str, Any], cwd: str) -> str:
        """根据工具名、参数和工作目录生成缓存键。"""
        data = {"tool": tool_name, "args": args, "cwd": cwd}
        normalized = json.dumps(data, sort_keys=True, ensure_ascii=True)
        return hashlib.md5(normalized.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Optional["ToolResult"]:
        """获取缓存结果，过期返回 None。"""
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
        result: "ToolResult",
        ttl: Optional[float] = None,
    ) -> None:
        """写入缓存。"""
        ttl = ttl if ttl is not None else self.default_ttl
        self._store[key] = _CachedEntry(
            result=result,
            expires_at=time.monotonic() + ttl,
        )

    def clear(self) -> None:
        """清空缓存。"""
        self._store.clear()
