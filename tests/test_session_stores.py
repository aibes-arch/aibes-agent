"""Tests for session store backends."""

from __future__ import annotations

import asyncio

import pytest

from aibes_agent.core.session import (
    FileSessionStore,
    MemorySessionStore,
    SessionState,
    SQLiteSessionStore,
)


@pytest.fixture(params=["memory", "file", "sqlite"])
def store(tmp_path, request):
    if request.param == "memory":
        return MemorySessionStore()
    if request.param == "file":
        return FileSessionStore(str(tmp_path / "sessions"))
    if request.param == "sqlite":
        return SQLiteSessionStore(str(tmp_path / "sessions.db"))
    raise ValueError(request.param)


@pytest.mark.asyncio
async def test_save_load_round_trip(store):
    state = SessionState(session_id="s1", messages=[{"role": "user", "content": "hi"}])
    await store.save(state)
    loaded = await store.load("s1")
    assert loaded is not None
    assert loaded.session_id == "s1"
    assert loaded.messages == [{"role": "user", "content": "hi"}]


@pytest.mark.asyncio
async def test_load_missing(store):
    assert await store.load("missing") is None


@pytest.mark.asyncio
async def test_list_sessions(store):
    await store.save(SessionState(session_id="a"))
    await store.save(SessionState(session_id="b"))
    assert await store.list_sessions() == ["a", "b"]


@pytest.mark.asyncio
async def test_delete(store):
    await store.save(SessionState(session_id="del-me"))
    assert await store.delete("del-me") is True
    assert await store.load("del-me") is None
    assert await store.delete("del-me") is False


@pytest.mark.asyncio
async def test_clear(store):
    await store.save(SessionState(session_id="x"))
    await store.save(SessionState(session_id="y"))
    await store.clear()
    assert await store.list_sessions() == []


@pytest.mark.asyncio
async def test_cleanup(store):
    await store.save(SessionState(session_id="old"))
    await asyncio.sleep(0.05)
    await store.save(SessionState(session_id="new"))
    deleted = await store.cleanup(max_age_seconds=0.03)
    assert deleted == 1
    assert await store.load("old") is None
    assert await store.load("new") is not None
