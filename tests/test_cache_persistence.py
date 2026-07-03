"""Tests for persistent tool result cache."""

from __future__ import annotations

import asyncio

import pytest

from aibes_agent.core.cache import SqliteToolResultCache
from aibes_agent.tools.base import ToolResult


@pytest.fixture
def cache(tmp_path):
    return SqliteToolResultCache(path=str(tmp_path / "cache.db"), default_ttl=60.0)


def test_sqlite_cache_set_get(cache):
    result = ToolResult.ok("hello", meta_key="meta_value")
    key = cache.make_key("FileRead", {"file_path": "/tmp/a.txt"}, "/tmp")
    cache.set(key, result)
    cached = cache.get(key)
    assert cached is not None
    assert cached.content == "hello"
    assert cached.metadata.get("meta_key") == "meta_value"


def test_sqlite_cache_expiration(tmp_path):
    cache = SqliteToolResultCache(path=str(tmp_path / "cache.db"), default_ttl=0.1)
    key = cache.make_key("FileRead", {"file_path": "/tmp/a.txt"}, "/tmp")
    cache.set(key, ToolResult.ok("hello"))
    assert cache.get(key) is not None
    asyncio.run(asyncio.sleep(0.15))
    assert cache.get(key) is None


def test_sqlite_cache_clear(cache):
    key = cache.make_key("FileRead", {"file_path": "/tmp/a.txt"}, "/tmp")
    cache.set(key, ToolResult.ok("hello"))
    cache.clear()
    assert cache.get(key) is None


def test_sqlite_cache_max_size(tmp_path):
    cache = SqliteToolResultCache(path=str(tmp_path / "cache.db"), default_ttl=60.0, max_size=2)
    for i in range(3):
        key = cache.make_key("FileRead", {"file_path": f"/tmp/{i}.txt"}, "/tmp")
        cache.set(key, ToolResult.ok(str(i)))
    keys = [cache.make_key("FileRead", {"file_path": f"/tmp/{i}.txt"}, "/tmp") for i in range(3)]
    # Oldest entry (0) should be evicted due to max_size.
    assert cache.get(keys[0]) is None
    assert cache.get(keys[1]) is not None
    assert cache.get(keys[2]) is not None
