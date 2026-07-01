import pytest

from minagent.core.cache import ToolResultCache
from minagent.core.tool_registry import ToolRegistry
from minagent.tools.base import ToolContext
from minagent.tools.fs import FileReadTool, FileWriteTool


@pytest.mark.asyncio
async def test_registry_caches_read_only_tool(tmp_path):
    registry = ToolRegistry()
    registry.register(FileReadTool())

    file = tmp_path / "hello.txt"
    file.write_text("world", encoding="utf-8")

    cache = ToolResultCache(default_ttl=60.0)
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

    cache = ToolResultCache(default_ttl=60.0)
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
