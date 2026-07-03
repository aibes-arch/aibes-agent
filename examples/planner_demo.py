"""Demonstrate the Planner tool for multi-step task execution."""

from __future__ import annotations

import asyncio
import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from aibes_agent import LLMClient, PermissionEngine, ToolContext, ToolRegistry
from aibes_agent.core.engine import AgentConfig, AgentLoop
from aibes_agent.core.session import FileSessionStore
from aibes_agent.planner import PlannerTool
from aibes_agent.tools import BashTool, FileReadTool, GlobTool, GrepTool


async def main() -> None:
    llm = LLMClient(
        base_url=os.getenv("OPENAI_BASE_URL", "http://192.168.2.179:1234/v1"),
        api_key=os.getenv("OPENAI_API_KEY", "dummy"),
        model=os.getenv("AIBES_AGENT_MODEL", "qwen/qwen3.6-35b-a3b"),
    )

    registry = ToolRegistry()
    registry.register(FileReadTool())
    registry.register(GlobTool())
    registry.register(GrepTool())
    registry.register(BashTool())
    registry.register(
        PlannerTool(
            llm=llm,
            registry=registry,
            permission_engine=PermissionEngine.default(),
            tool_context=ToolContext(cwd=os.getcwd()),
        )
    )

    agent = AgentLoop(
        llm=llm,
        registry=registry,
        config=AgentConfig(system_prompt="Use the Planner tool for complex multi-step tasks."),
        permission_engine=PermissionEngine.default(),
        tool_context=ToolContext(cwd=os.getcwd()),
        session_store=FileSessionStore(".aibes-agent/sessions"),
    )

    task = (
        "请列出 aibes_agent 目录下的所有 Python 文件，并总结每个文件的主要职责。"
        "使用 Planner 工具制定计划并执行。"
    )
    print(f"Task: {task}\n")

    async for event in agent.run(task, session_id="planner-demo"):
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
    asyncio.run(main())
