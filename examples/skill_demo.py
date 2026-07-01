"""Demonstrate loading a skill and running an agent with it."""

from __future__ import annotations

import asyncio
import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from aibes_agent import LLMClient, PermissionEngine, ToolContext, ToolRegistry
from aibes_agent.core.engine import AgentConfig, AgentLoop
from aibes_agent.skills import SkillBuilder, SkillLoader
from aibes_agent.tools import (
    BashTool,
    FileReadTool,
    GrepTool,
    GlobTool,
)


async def main():
    # 1. Configure LLM
    llm = LLMClient(
        base_url=os.getenv("OPENAI_BASE_URL", "http://192.168.2.179:1234/v1"),
        api_key=os.getenv("OPENAI_API_KEY", "dummy"),
        model=os.getenv("AIBES_AGENT_MODEL", "qwen/qwen3.6-35b-a3b"),
    )

    # 2. Built-in tools available to skills
    tool_pool = {
        "FileRead": FileReadTool(),
        "Bash": BashTool(),
        "Grep": GrepTool(),
        "Glob": GlobTool(),
    }

    # 3. Load skills from .aibes-agent/skills
    skills = SkillLoader().load_all()
    print(f"Loaded skills: {[s.name for s in skills]}")

    builder = SkillBuilder(skills, tool_pool)
    agent_config, registry, profiles = builder.build()

    # 4. Create the agent
    agent = AgentLoop(
        llm=llm,
        registry=registry,
        config=agent_config,
        permission_engine=PermissionEngine.default(),
        tool_context=ToolContext(cwd=os.getcwd()),
    )

    task = "请查看 aibes_agent 项目结构，列出所有 Python 文件，并给出简要说明。"
    print(f"Task: {task}\n")

    async for event in agent.run(task):
        if event["type"] == "llm_response":
            print(f"\n[LLM Turn {event['turn']} - {event.get('model', '')}]\n{event['content']}")
            if event["tool_calls"]:
                names = [tc["function"]["name"] for tc in event["tool_calls"]]
                print(f"Tool calls: {names}")
        elif event["type"] == "tool_result":
            print(f"\n[Tool: {event['name']}]\n{event['content'][:500]}")
        elif event["type"] == "final":
            print(f"\n[Final]\n{event['content']}")
            stats = event.get("stats")
            if stats:
                print(
                    f"\n[Stats] turns={stats['turn_count']} "
                    f"llm_calls={stats['llm_call_count']} "
                    f"tool_calls={stats['tool_call_count']} "
                    f"tokens={stats['total_tokens']}"
                )
        elif event["type"] == "error":
            print(f"\n[Error] {event['message']}")


if __name__ == "__main__":
    asyncio.run(main())
