import asyncio

import pytest

from aibes_agent.core.cache import MemoryToolResultCache, SqliteToolResultCache, ToolResultCache
from aibes_agent.tools.base import ToolResult


@pytest.mark.asyncio
async def test_cache_set_get():
    cache = MemoryToolResultCache(default_ttl=60.0)
    result = ToolResult.ok("hello")
    key = cache.make_key("FileRead", {"file_path": "/tmp/a.txt"}, "/tmp")

    cache.set(key, result)
    cached = cache.get(key)

    assert cached is not None
    assert cached.content == "hello"


@pytest.mark.asyncio
async def test_cache_expiration():
    cache = MemoryToolResultCache(default_ttl=0.01)
    result = ToolResult.ok("hello")
    key = cache.make_key("FileRead", {"file_path": "/tmp/a.txt"}, "/tmp")

    cache.set(key, result)
    await asyncio.sleep(0.02)
    cached = cache.get(key)
    assert cached is None


@pytest.mark.asyncio
async def test_cache_clear():
    cache = MemoryToolResultCache()
    cache.set("k", ToolResult.ok("v"))
    cache.clear()
    assert cache.get("k") is None


@pytest.mark.asyncio
async def test_cache_key_differs_by_args():
    cache = MemoryToolResultCache()
    k1 = cache.make_key("Glob", {"pattern": "*.py"}, "/tmp")
    k2 = cache.make_key("Glob", {"pattern": "*.md"}, "/tmp")
    assert k1 != k2


def test_tool_result_cache_abstract():
    assert issubclass(MemoryToolResultCache, ToolResultCache)
    assert issubclass(SqliteToolResultCache, ToolResultCache)
