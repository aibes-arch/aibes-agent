"""Tools for agent long-term memory."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from aibes_agent.memory.store import MemoryStore
from aibes_agent.tools.base import Tool, ToolContext, ToolResult


class SaveMemoryInput(BaseModel):
    text: str = Field(..., description="Text to remember.")
    topic: str = Field("", description="Optional topic tag.")


class SearchMemoryInput(BaseModel):
    query: str = Field(..., description="Query to search memory.")
    top_k: int = Field(5, description="Number of results to return.")


class SaveMemoryTool(Tool[SaveMemoryInput]):
    name = "SaveMemory"
    description = "Save a piece of information to long-term memory."
    input_model = SaveMemoryInput

    def __init__(self, store: MemoryStore) -> None:
        super().__init__()
        self.store = store

    def is_read_only(self, input: SaveMemoryInput) -> bool:
        return False

    async def call(self, input: SaveMemoryInput, context: ToolContext) -> ToolResult:
        metadata: dict = {}
        if input.topic:
            metadata["topic"] = input.topic
        entry_id = self.store.add(input.text, metadata)
        return ToolResult.ok(f"Saved memory with id {entry_id}")


class SearchMemoryTool(Tool[SearchMemoryInput]):
    name = "SearchMemory"
    description = "Search long-term memory for relevant information."
    input_model = SearchMemoryInput

    def __init__(self, store: MemoryStore) -> None:
        super().__init__()
        self.store = store

    def is_read_only(self, input: SearchMemoryInput) -> bool:
        return True

    async def call(self, input: SearchMemoryInput, context: ToolContext) -> ToolResult:
        entries = self.store.search(input.query, top_k=input.top_k)
        if not entries:
            return ToolResult.ok("No relevant memories found.")
        lines = []
        for entry in entries:
            lines.append(f"- {entry.text}")
        return ToolResult.ok("\n".join(lines))


def build_memory_tools(store: Optional[MemoryStore] = None) -> list[Tool]:
    """Build memory tools bound to *store*.

    If *store* is None, an ``InMemoryMemoryStore`` is used.
    """
    if store is None:
        from aibes_agent.memory.store import InMemoryMemoryStore

        store = InMemoryMemoryStore()
    return [SaveMemoryTool(store), SearchMemoryTool(store)]
