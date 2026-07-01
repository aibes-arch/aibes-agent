import pytest

from aibes_agent.core.context import ContextWindow, Message
from aibes_agent.core.session import (
    FileSessionStore,
    SessionState,
    context_from_session,
    session_from_context,
)


@pytest.mark.asyncio
async def test_file_session_store_save_load(tmp_path):
    store = FileSessionStore(str(tmp_path / "sessions"))
    state = SessionState(
        session_id="sess-1",
        messages=[{"role": "user", "content": "hi"}],
        tasks=[{"id": 1, "description": "task"}],
    )
    await store.save(state)
    loaded = await store.load("sess-1")
    assert loaded is not None
    assert loaded.session_id == "sess-1"
    assert loaded.messages == state.messages
    assert loaded.tasks == state.tasks


@pytest.mark.asyncio
async def test_file_session_store_list(tmp_path):
    store = FileSessionStore(str(tmp_path / "sessions"))
    await store.save(SessionState(session_id="a"))
    await store.save(SessionState(session_id="b"))
    assert await store.list_sessions() == ["a", "b"]


@pytest.mark.asyncio
async def test_file_session_store_missing(tmp_path):
    store = FileSessionStore(str(tmp_path / "sessions"))
    assert await store.load("missing") is None


def test_context_round_trip():
    ctx = ContextWindow()
    ctx.add(Message(role="system", content="sys"))
    ctx.add(Message(role="user", content="hello"))
    state = session_from_context("s", ctx)
    restored = context_from_session(state)
    assert len(restored.messages) == 2
    assert restored.messages[0].role == "system"
    assert restored.messages[1].content == "hello"
