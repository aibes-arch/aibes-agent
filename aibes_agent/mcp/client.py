"""MCP client: manage connections to multiple MCP servers and expose their tools."""

from __future__ import annotations

from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.sse import sse_client
    from mcp.client.stdio import stdio_client
except ImportError as exc:
    raise ImportError(
        "MCP support requires the 'mcp' package. " "Install it with: pip install aibes_agent[mcp]"
    ) from exc

from aibes_agent.config import MCPServerConfig
from aibes_agent.mcp.tool import MCPTool


class MCPClient:
    """Manage one or more MCP server sessions and aggregate their tools."""

    def __init__(
        self,
        configs: Dict[str, MCPServerConfig],
        name_prefix: str = "mcp",
    ) -> None:
        self.configs = configs
        self.name_prefix = name_prefix
        self._exit_stack = AsyncExitStack()
        self._sessions: Dict[str, ClientSession] = {}
        self._tools: Dict[str, Dict[str, Any]] = {}

    async def __aenter__(self) -> "MCPClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.close()

    async def connect(self) -> None:
        """Connect to all configured MCP servers and initialize sessions."""
        for name, cfg in self.configs.items():
            if cfg.transport == "stdio":
                params = StdioServerParameters(
                    command=cfg.command or "",
                    args=cfg.args,
                    env=cfg.env or None,
                )
                transport = await self._exit_stack.enter_async_context(stdio_client(params))
            elif cfg.transport == "sse":
                if not cfg.url:
                    raise ValueError(f"MCP server '{name}' with sse transport requires a url")
                transport = await self._exit_stack.enter_async_context(sse_client(url=cfg.url))
            else:
                raise ValueError(f"Unsupported MCP transport '{cfg.transport}' for server '{name}'")

            read, write, *_ = transport
            session = await self._exit_stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            self._sessions[name] = session

    async def close(self) -> None:
        """Close all sessions and transports."""
        await self._exit_stack.aclose()
        self._sessions.clear()
        self._tools.clear()

    async def list_tools(self) -> Dict[str, Dict[str, Any]]:
        """Discover tools from all servers and return a map of prefixed tool names."""
        tools: Dict[str, Dict[str, Any]] = {}
        for server_name, session in self._sessions.items():
            response = await session.list_tools()
            for tool in response.tools:
                prefixed = f"{self.name_prefix}_{server_name}_{tool.name}"
                tools[prefixed] = {
                    "server": server_name,
                    "tool_name": tool.name,
                    "description": tool.description or "",
                    "schema": tool.inputSchema or {"type": "object"},
                }
        self._tools = tools
        return tools

    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool on a specific MCP server."""
        session = self._sessions.get(server_name)
        if session is None:
            raise ValueError(f"MCP server '{server_name}' is not connected")
        return await session.call_tool(tool_name, arguments=arguments)

    async def get_tools(self) -> Dict[str, MCPTool]:
        """Return MCPTool instances for all discovered tools."""
        if not self._tools:
            await self.list_tools()
        result: Dict[str, MCPTool] = {}
        for prefixed, info in self._tools.items():
            result[prefixed] = MCPTool(
                server_name=info["server"],
                tool_name=info["tool_name"],
                description=info["description"],
                schema=info["schema"],
                client=self,
            )
        return result

    def list_server_names(self) -> List[str]:
        return list(self._sessions.keys())
