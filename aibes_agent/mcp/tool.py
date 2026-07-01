"""Wrap an MCP tool as a aibes_agent Tool."""

from __future__ import annotations

from typing import Any, Dict, TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from aibes_agent.tools.base import Tool, ToolContext, ToolResult

if TYPE_CHECKING:
    from aibes_agent.mcp.client import MCPClient


class MCPToolInput(BaseModel):
    """Generic input that accepts any fields defined by the MCP tool schema."""

    model_config = ConfigDict(extra="allow")


class MCPTool(Tool[MCPToolInput]):
    """Adapter exposing an MCP server tool to aibes_agent's ToolRegistry."""

    input_model = MCPToolInput

    def __init__(
        self,
        server_name: str,
        tool_name: str,
        description: str,
        schema: Dict[str, Any],
        client: "MCPClient",
        read_only: bool = False,
    ) -> None:
        self.server_name = server_name
        self.tool_name = tool_name
        self._tool_description = description
        self._schema = schema
        self._client = client
        self._read_only = read_only
        self.name = f"mcp_{server_name}_{tool_name}"
        super().__init__()

    @property
    def description(self) -> str:  # type: ignore[override]
        return self._tool_description

    @description.setter
    def description(self, value: str) -> None:
        self._tool_description = value

    def to_openai_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self._tool_description,
                "parameters": self._schema,
            },
        }

    def is_read_only(self, input: MCPToolInput) -> bool:
        return self._read_only

    async def call(self, input: MCPToolInput, context: ToolContext) -> ToolResult:
        try:
            result = await self._client.call_tool(
                self.server_name,
                self.tool_name,
                input.model_dump(),
            )
        except Exception as exc:
            return ToolResult.fail(f"MCP tool '{self.name}' failed: {exc}")

        if getattr(result, "isError", False):
            text = _extract_text(result)
            return ToolResult.fail(text or "MCP tool returned an error")

        return ToolResult.ok(_extract_text(result))


def _extract_text(result: Any) -> str:
    parts: list[str] = []
    for item in getattr(result, "content", []) or []:
        text = getattr(item, "text", None)
        if text is not None:
            parts.append(str(text))
        else:
            parts.append(str(item))
    return "\n".join(parts)
