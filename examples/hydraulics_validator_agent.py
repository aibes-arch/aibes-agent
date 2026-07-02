"""Drilling hydraulics formula validator demo."""

import asyncio
import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from aibes_agent import (
    AgentConfig,
    AgentLoop,
    BashTool,
    FileReadTool,
    GlobTool,
    LLMClient,
    PermissionEngine,
    PermissionRule,
    QueryKnowledgeBaseTool,
    ToolContext,
    ToolRegistry,
    ValidateFormulaTool,
)


async def main():
    llm = LLMClient(
        base_url=os.getenv("OPENAI_BASE_URL", "http://192.168.2.179:1234/v1"),
        api_key=os.getenv("OPENAI_API_KEY", "dummy"),
        model=os.getenv("AIBES_AGENT_MODEL", "qwen3-coder-plus-32k"),
    )

    registry = ToolRegistry()
    registry.register_many(
        [
            FileReadTool(),
            BashTool(),
            GlobTool(),
            ValidateFormulaTool(),
            QueryKnowledgeBaseTool(),
        ]
    )

    config = AgentConfig(
        system_prompt=(
            "You are a drilling hydraulics expert. Help users validate formulas, check unit "
            "conversions, and look up relevant standards and incident cases. Be precise and "
            "cite the knowledge base when applicable."
        ),
        max_turns=10,
    )

    perm = PermissionEngine(
        rules=[
            PermissionRule("allow", "tool", "FileRead"),
            PermissionRule("allow", "tool", "Glob"),
            PermissionRule("allow", "tool", "Bash"),
            PermissionRule("allow", "tool", "ValidateFormula"),
            PermissionRule("allow", "tool", "QueryKnowledgeBase"),
        ],
        mode="auto",
    )

    agent = AgentLoop(
        llm=llm,
        registry=registry,
        config=config,
        permission_engine=perm,
        tool_context=ToolContext(cwd=os.getcwd()),
    )

    task = (
        "请验证 ECD（当量循环密度）公式，使用 rho=1200 kg/m3, g=9.81 m/s2, TVD=2000 m，"
        "并将结果换算为 ppg。同时查询知识库给出安全建议。"
    )

    async for event in agent.run(task):
        if event["type"] == "llm_response":
            print(f"\n[LLM Turn {event['turn']}]")
            if event["content"]:
                print(event["content"])
            if event["tool_calls"]:
                names = [tc["function"]["name"] for tc in event["tool_calls"]]
                print(f"Tool calls: {names}")
        elif event["type"] == "tool_result":
            print(f"\n[Tool: {event['name']}]\n{event['content'][:500]}")
        elif event["type"] == "final":
            print(f"\n{'='*60}\n[分析结果]\n{event['content']}")
        elif event["type"] == "error":
            print(f"\n[Error] {event['message']}")


if __name__ == "__main__":
    asyncio.run(main())
