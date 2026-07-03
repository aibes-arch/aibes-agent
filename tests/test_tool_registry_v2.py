import pytest

from pydantic import BaseModel

from aibes_agent.core.cache import MemoryToolResultCache
from aibes_agent.core.tool_registry import ToolRegistry
from aibes_agent.tools.base import Tool, ToolContext, ToolResult
from aibes_agent.tools.fs import FileReadTool, FileWriteTool


class ExplodeInput(BaseModel):
    pass


class ExplodingTool(Tool[ExplodeInput]):
    name = "Explode"
    description = "Always raises an exception"
    input_model = ExplodeInput

    def is_read_only(self, input: ExplodeInput) -> bool:
        return False

    async def call(self, input: ExplodeInput, context: ToolContext) -> ToolResult:
        raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_registry_caches_read_only_tool(tmp_path):
    registry = ToolRegistry()
    registry.register(FileReadTool())

    file = tmp_path / "hello.txt"
    file.write_text("world", encoding="utf-8")

    cache = MemoryToolResultCache(default_ttl=60.0)
    ctx = ToolContext(cwd=str(tmp_path), cache=cache)

    tool_call = {
        "id": "call_1",
        "type": "function",
        "function": {
            "name": "FileRead",
            "arguments": {"file_path": str(file)},
        },
    }

    results1 = await registry.execute([tool_call], ctx)
    assert results1[0]["content"] == "world"

    # 修改文件内容，第二次仍应从缓存读取旧结果
    file.write_text("changed", encoding="utf-8")
    results2 = await registry.execute([tool_call], ctx)
    assert results2[0]["content"] == "world"


@pytest.mark.asyncio
async def test_registry_does_not_cache_write_tool(tmp_path):
    registry = ToolRegistry()
    registry.register(FileWriteTool())

    cache = MemoryToolResultCache(default_ttl=60.0)
    ctx = ToolContext(cwd=str(tmp_path), cache=cache)

    file = tmp_path / "out.txt"
    tool_call = {
        "id": "call_1",
        "type": "function",
        "function": {
            "name": "FileWrite",
            "arguments": {"file_path": str(file), "content": "first"},
        },
    }

    await registry.execute([tool_call], ctx)
    assert file.read_text(encoding="utf-8") == "first"

    tool_call["function"]["arguments"]["content"] = "second"
    await registry.execute([tool_call], ctx)
    assert file.read_text(encoding="utf-8") == "second"


@pytest.mark.asyncio
async def test_registry_validation_error():
    registry = ToolRegistry()
    registry.register(FileReadTool())
    ctx = ToolContext(cwd="/")

    tool_call = {
        "id": "call_1",
        "type": "function",
        "function": {
            "name": "FileRead",
            "arguments": {"missing_required": "value"},
        },
    }

    results = await registry.execute([tool_call], ctx)
    assert not results[0]["content"].startswith("Error:")
    assert (
        "validation error" in results[0]["content"].lower()
        or "Input validation error" in results[0]["content"]
    )


@pytest.mark.asyncio
async def test_registry_unknown_tool():
    registry = ToolRegistry()
    ctx = ToolContext(cwd="/")

    tool_call = {
        "id": "call_1",
        "type": "function",
        "function": {"name": "UnknownTool", "arguments": {}},
    }

    results = await registry.execute([tool_call], ctx)
    assert "Error:" in results[0]["content"]


@pytest.mark.asyncio
async def test_registry_sequential_exception_handled():
    registry = ToolRegistry()
    registry.register(ExplodingTool())
    ctx = ToolContext(cwd="/")

    tool_call = {
        "id": "call_1",
        "type": "function",
        "function": {"name": "Explode", "arguments": {}},
    }

    results = await registry.execute([tool_call], ctx)
    assert "Error:" in results[0]["content"]
    assert "boom" in results[0]["content"]


@pytest.mark.asyncio
async def test_registry_concurrent_exception_handled():
    registry = ToolRegistry()
    registry.register(ExplodingTool())
    ctx = ToolContext(cwd="/")

    tool_calls = [
        {
            "id": f"call_{i}",
            "type": "function",
            "function": {"name": "Explode", "arguments": {}},
        }
        for i in range(2)
    ]

    results = await registry.execute(tool_calls, ctx)
    assert len(results) == 2
    for r in results:
        assert "Error:" in r["content"]


@pytest.mark.asyncio
async def test_registry_result_error_formatting():
    registry = ToolRegistry()
    ctx = ToolContext(cwd="/")

    # Use private method to test formatting
    result = ToolResult.fail("something failed", content="partial")
    formatted = registry._result_to_dict("id", "Tool", result)
    assert formatted["tool_call_id"] == "id"
    assert "something failed" in formatted["content"]
