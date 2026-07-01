"""v0.2.0 子 Agent 演示。

本示例展示如何让父 Agent 调用一个专门负责“代码探索”的子 Agent。
"""

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
    GlobTool,
    GrepTool,
    LLMClient,
    PermissionEngine,
    TaskListTool,
    ToolContext,
    ToolRegistry,
)


async def main():
    llm = LLMClient(
        base_url=os.getenv("OPENAI_BASE_URL", "http://192.168.2.179:1234/v1"),
        api_key=os.getenv("OPENAI_API_KEY", "dummy"),
        model=os.getenv("AIBES_AGENT_MODEL", "qwen3-coder-plus-32k"),
    )

    file_read = FileReadTool()
    grep = GrepTool()
    glob = GlobTool()
    bash = BashTool()
    task_list = TaskListTool()

    tool_pool = {
        "FileRead": file_read,
        "Grep": grep,
        "Glob": glob,
        "Bash": bash,
    }

    agent_tool = AgentTool(
        profiles={
            "default": AgentProfile(
                name="default",
                system_prompt="You are a helpful assistant.",
                tools=["Glob", "Grep", "FileRead"],
                max_turns=5,
            ),
            "researcher": AgentProfile(
                name="researcher",
                system_prompt=(
                    "You are a code exploration specialist. "
                    "Use Glob, Grep and FileRead to investigate the project, "
                    "then return a concise summary of the project structure and purpose."
                ),
                tools=["Glob", "Grep", "FileRead"],
                max_turns=5,
            ),
        },
        llm=llm,
        tool_pool=tool_pool,
    )

    registry = ToolRegistry()
    registry.register_many(
        [
            file_read,
            grep,
            glob,
            bash,
            task_list,
            agent_tool,
        ]
    )

    config = AgentConfig(
        system_prompt="""You are a helpful coding assistant.
You can use the Agent tool to delegate code exploration tasks to a sub-agent.
When given a task, decide whether to handle it yourself or delegate it.
""",
        max_turns=10,
    )

    perm = PermissionEngine.default()
    tool_context = ToolContext(cwd=os.getcwd())

    agent = AgentLoop(
        llm=llm,
        registry=registry,
        config=config,
        permission_engine=perm,
        tool_context=tool_context,
    )

    task = "请让 researcher 子 Agent 探索 aibes_agent 项目，列出 Python 文件并给出项目说明。"
    print(f"Task: {task}\n")
    print("=" * 60)

    async for event in agent.run(task):
        if event["type"] == "llm_response":
            print(f"\n[LLM Turn {event['turn']}]\n{event['content']}")
            if event["tool_calls"]:
                print(f"Tool calls: {[tc['function']['name'] for tc in event['tool_calls']]}")
        elif event["type"] == "tool_result":
            print(f"\n[Tool: {event['name']}]\n{event['content'][:500]}")
        elif event["type"] == "final":
            print(f"\n[Final]\n{event['content']}")
            stats = event.get("stats")
            if stats:
                print(
                    f"\n[Stats] turns={stats['turn_count']} llm_calls={stats['llm_call_count']} "
                    f"tool_calls={stats['tool_call_count']} tokens={stats['total_tokens']}"
                )
        elif event["type"] == "error":
            print(f"\n[Error] {event['message']}")


if __name__ == "__main__":
    asyncio.run(main())
