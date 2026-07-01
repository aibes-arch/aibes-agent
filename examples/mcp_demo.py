"""Demonstrate connecting to an MCP server (filesystem) and using its tools."""

from __future__ import annotations

import asyncio
import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from aibes_agent import LLMClient, PermissionEngine, ToolContext, ToolRegistry
from aibes_agent.config import MCPServerConfig
from aibes_agent.core.engine import AgentConfig, AgentLoop
from aibes_agent.mcp.client import MCPClient


async def main():
    llm = LLMClient(
        base_url=os.getenv("OPENAI_BASE_URL", "http://192.168.2.179:1234/v1"),
        api_key=os.getenv("OPENAI_API_KEY", "dummy"),
        model=os.getenv("AIBES_AGENT_MODEL", "qwen/qwen3.6-35b-a3b"),
    )

    cwd = os.getcwd()
    mcp_client = MCPClient(
        {
            "filesystem": MCPServerConfig(
                transport="stdio",
                command="npx",
                args=["-y", "@modelcontextprotocol/server-filesystem", cwd],
            )
        }
    )

    async with mcp_client:
        mcp_tools = await mcp_client.get_tools()
        print(f"Discovered MCP tools: {list(mcp_tools.keys())}")

        registry = ToolRegistry()
        for tool in mcp_tools.values():
            registry.register(tool)

        agent = AgentLoop(
            llm=llm,
            registry=registry,
            config=AgentConfig(
                system_prompt="You have access to a filesystem MCP server. "
                "Use its tools when asked about files.",
                max_turns=10,
            ),
            permission_engine=PermissionEngine.default(),
            tool_context=ToolContext(cwd=cwd),
        )

        task = f"List the Python files in {cwd} using the available tools."
        print(f"Task: {task}\n")

        async for event in agent.run(task):
            if event["type"] == "llm_response":
                print(f"\n[LLM Turn {event['turn']}]\n{event['content']}")
                if event["tool_calls"]:
                    names = [tc["function"]["name"] for tc in event["tool_calls"]]
                    print(f"Tool calls: {names}")
            elif event["type"] == "tool_result":
                print(f"\n[Tool: {event['name']}]\n{event['content'][:1000]}")
            elif event["type"] == "final":
                print(f"\n[Final]\n{event['content']}")
            elif event["type"] == "error":
                print(f"\n[Error] {event['message']}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        print(f"MCP demo failed: {exc}", file=sys.stderr)
        sys.exit(1)
