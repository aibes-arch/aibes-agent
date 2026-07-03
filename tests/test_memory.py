"""Tests for memory store and memory tools."""

from __future__ import annotations

import pytest

from aibes_agent.memory import InMemoryMemoryStore, build_memory_tools
from aibes_agent.memory.store import MemoryEntry
from aibes_agent.tools.base import ToolContext


@pytest.fixture
def store():
    return InMemoryMemoryStore()


def test_add_and_search(store):
    store.add("Python is great for Agent development.", {"topic": "python"})
    store.add("JavaScript runs in browsers.", {"topic": "js"})
    results = store.search("Python Agent", top_k=2)
    assert len(results) == 1
    assert "Python" in results[0].text


def test_search_no_match(store):
    store.add("Some unrelated text.")
    assert store.search("machine learning") == []


def test_delete(store):
    entry_id = store.add("Remember this.")
    assert store.delete(entry_id) is True
    assert store.delete(entry_id) is False
    assert store.search("Remember") == []


def test_clear(store):
    store.add("A")
    store.add("B")
    store.clear()
    assert store.search("A") == []


@pytest.mark.asyncio
async def test_memory_tools(store):
    save_tool, search_tool = build_memory_tools(store)
    ctx = ToolContext(cwd="/")

    save_result = await save_tool.call(
        save_tool.input_model(text="aibes-agent supports plugins."),
        ctx,
    )
    assert "Saved memory" in save_result.content

    search_result = await search_tool.call(
        search_tool.input_model(query="plugins support"),
        ctx,
    )
    assert "aibes-agent supports plugins" in search_result.content


def test_memory_entry_dataclass():
    entry = MemoryEntry(id="1", text="hello", metadata={"k": "v"})
    assert entry.text == "hello"
