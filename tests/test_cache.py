import pytest

from minagent.core.cache import ToolResultCache
from minagent.tools.base import ToolResult


@pytest.mark.asyncio
async def test_cache_set_get():
    cache = ToolResultCache(default_ttl=60.0)
    result = ToolResult.ok("hello")
    key = cache.make_key("FileRead", {"file_path": "/tmp/a.txt"}, "/tmp")

    cache.set(key, result)
    cached = cache.get(key)

    assert cached is not None
    assert cached.content == "hello"


@pytest.mark.asyncio
async def test_cache_expiration():
    cache = ToolResultCache(default_ttl=0.01)
    result = ToolResult.ok("hello")
    key = cache.make_key("FileRead", {"file_path": "/tmp/a.txt"}, "/tmp")

    cache.set(key, result)
    import asyncio

    await asyncio.sleep(0.02)
    cached = cache.get(key)
    assert cached is None


@pytest.mark.asyncio
async def test_cache_clear():
    cache = ToolResultCache()
    cache.set("k", ToolResult.ok("v"))
    cache.clear()
    assert cache.get("k") is None


@pytest.mark.asyncio
async def test_cache_key_differs_by_args():
    cache = ToolResultCache()
    k1 = cache.make_key("Glob", {"pattern": "*.py"}, "/tmp")
    k2 = cache.make_key("Glob", {"pattern": "*.md"}, "/tmp")
    assert k1 != k2
