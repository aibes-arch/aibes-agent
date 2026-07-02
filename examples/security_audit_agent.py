"""Security audit Agent demo using the code-review skill security profile."""

import asyncio
import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from aibes_agent import (
    AgentConfig,
    AgentLoop,
    AgentProfile,
    AgentTool,
    BashTool,
    FileReadTool,
    GitDiffTool,
    GlobTool,
    GrepTool,
    LLMClient,
    LintTool,
    PermissionEngine,
    PermissionRule,
    ToolContext,
    ToolRegistry,
)


async def main():
    llm = LLMClient(
        base_url=os.getenv("OPENAI_BASE_URL", "http://192.168.2.179:1234/v1"),
        api_key=os.getenv("OPENAI_API_KEY", "dummy"),
        model=os.getenv("AIBES_AGENT_MODEL", "qwen3-coder-plus-32k"),
    )

    tool_pool = {
        "FileRead": FileReadTool(),
        "Grep": GrepTool(),
        "Glob": GlobTool(),
        "Bash": BashTool(),
        "GitDiff": GitDiffTool(),
        "Lint": LintTool(),
    }

    agent_tool = AgentTool(
        profiles={
            "security": AgentProfile(
                name="security",
                system_prompt=(
                    "You are a security auditor. Focus exclusively on injection risks, "
                    "unsafe deserialization, hardcoded secrets, path traversal, and other "
                    "common vulnerabilities. Be specific and cite file paths and line numbers."
                ),
                tools=["FileRead", "Grep", "GitDiff"],
                max_turns=5,
            ),
        }
    )

    registry = ToolRegistry()
    registry.register_many(list(tool_pool.values()) + [agent_tool])

    config = AgentConfig(
        system_prompt=(
            "Audit the current project for security issues. Use the security sub-agent "
            "to inspect changed files and search for dangerous patterns. Output a structured report."
        ),
        max_turns=10,
    )

    perm = PermissionEngine(
        rules=[
            PermissionRule("allow", "tool", "FileRead"),
            PermissionRule("allow", "tool", "Grep"),
            PermissionRule("allow", "tool", "Glob"),
            PermissionRule("allow", "tool", "Bash"),
            PermissionRule("allow", "tool", "GitDiff"),
            PermissionRule("allow", "tool", "Lint"),
            PermissionRule("allow", "tool", "Agent"),
            PermissionRule("allow", "shell", "git .*"),
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

    async for event in agent.run("请对当前项目做安全审计，输出安全审查报告。"):
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
            print(f"\n{'='*60}\n[安全审计报告]\n{event['content']}")
        elif event["type"] == "error":
            print(f"\n[Error] {event['message']}")


if __name__ == "__main__":
    asyncio.run(main())
