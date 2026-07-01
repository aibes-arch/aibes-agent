from typing import Any, AsyncIterator, Dict, List

import pytest

from aibes_agent.config import MCPServerConfig
from aibes_agent.mcp.client import MCPClient
from aibes_agent.mcp.tool import MCPTool


class FakeTool:
    def __init__(self, name: str, description: str, schema: Dict[str, Any]):
        self.name = name
        self.description = description
        self.inputSchema = schema


class FakeListToolsResponse:
    def __init__(self, tools: List[FakeTool]):
        self.tools = tools


class FakeCallToolResult:
    def __init__(self, content: List[Any], is_error: bool = False):
        self.content = content
        self.isError = is_error


class FakeTextContent:
    def __init__(self, text: str):
        self.text = text
        self.type = "text"


class FakeSession:
    def __init__(self, *args: Any, **kwargs: Any):
        self.tools = [
            FakeTool(
                "read_file",
                "Read a file",
                {"type": "object", "properties": {"path": {"type": "string"}}},
            )
        ]
        self.next_result: Any = None

    async def initialize(self) -> None:
        pass

    async def list_tools(self) -> FakeListToolsResponse:
        return FakeListToolsResponse(self.tools)

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> FakeCallToolResult:
        if self.next_result is not None:
            return self.next_result
        return FakeCallToolResult([FakeTextContent(f"Result for {name}: {arguments.get('path')}")])

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass


class FakeStdioClient:
    def __init__(self, *args: Any, **kwargs: Any):
        pass

    async def __aenter__(self) -> tuple[Any, Any]:
        return (None, None)

    async def __aexit__(self, *args: Any) -> None:
        pass


@pytest.fixture
def patched_mcp(monkeypatch):
    monkeypatch.setattr("aibes_agent.mcp.client.ClientSession", FakeSession)
    monkeypatch.setattr("aibes_agent.mcp.client.stdio_client", FakeStdioClient)


@pytest.mark.asyncio
async def test_mcp_client_connect_and_list_tools(patched_mcp):
    client = MCPClient({"fs": MCPServerConfig(transport="stdio", command="echo", args=["hi"])})
    async with client:
        tools = await client.list_tools()
        assert "mcp_fs_read_file" in tools
        assert tools["mcp_fs_read_file"]["description"] == "Read a file"


@pytest.mark.asyncio
async def test_mcp_client_call_tool(patched_mcp):
    client = MCPClient({"fs": MCPServerConfig(transport="stdio", command="echo", args=["hi"])})
    async with client:
        result = await client.call_tool("fs", "read_file", {"path": "/tmp/test.txt"})
        assert any("/tmp/test.txt" in c.text for c in result.content)


@pytest.mark.asyncio
async def test_mcp_tool_schema_and_call(patched_mcp):
    client = MCPClient({"fs": MCPServerConfig(transport="stdio", command="echo", args=["hi"])})
    async with client:
        tools = await client.get_tools()
        assert "mcp_fs_read_file" in tools
        tool = tools["mcp_fs_read_file"]
        assert isinstance(tool, MCPTool)
        schema = tool.to_openai_schema()
        assert schema["function"]["name"] == "mcp_fs_read_file"
        assert schema["function"]["parameters"]["type"] == "object"

        from aibes_agent.tools.base import ToolContext

        result = await tool.call(
            tool.input_model(path="/tmp/test.txt"),
            ToolContext(cwd="/"),
        )
        assert result.success
        assert "/tmp/test.txt" in result.content


@pytest.mark.asyncio
async def test_mcp_tool_handles_error(patched_mcp):
    client = MCPClient({"fs": MCPServerConfig(transport="stdio", command="echo", args=["hi"])})
    async with client:
        tools = await client.get_tools()
        tool = tools["mcp_fs_read_file"]
        tool._client._sessions["fs"].next_result = FakeCallToolResult(
            [FakeTextContent("boom")], is_error=True
        )
        from aibes_agent.tools.base import ToolContext

        result = await tool.call(tool.input_model(path="/x"), ToolContext(cwd="/"))
        assert not result.success
        assert "boom" in result.error
