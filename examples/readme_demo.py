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
    FileWriteTool,
    GlobTool,
    GrepTool,
    LLMClient,
    PermissionEngine,
    TaskListTool,
    ToolContext,
    ToolRegistry,
)


async def main():
    # 1. 配置 LLM
    llm = LLMClient(
        base_url=os.getenv("OPENAI_BASE_URL", "http://192.168.2.179:1234/v1"),
        api_key=os.getenv("OPENAI_API_KEY", "dummy"),
        model=os.getenv("AIBES_AGENT_MODEL", "qwen3-coder-plus-32k"),
    )

    # 2. 创建工具注册表
    registry = ToolRegistry()
    registry.register_many(
        [
            FileReadTool(),
            FileWriteTool(),
            BashTool(),
            GrepTool(),
            GlobTool(),
            TaskListTool(),
        ]
    )

    # 3. 配置 Agent
    config = AgentConfig(
        system_prompt="""You are a helpful coding assistant. You can read files, run shell commands, search code, and manage tasks.

When given a task, break it down into steps, use tools to gather information, and explain your reasoning concisely.
""",
        max_turns=15,
    )

    # 4. 权限引擎
    perm = PermissionEngine.default()

    # 5. 工具上下文
    # 使用当前工作目录，避免在 Windows 上写死 Unix 风格路径
    tool_context = ToolContext(cwd=os.getcwd())

    # 6. 运行 Agent
    agent = AgentLoop(
        llm=llm,
        registry=registry,
        config=config,
        permission_engine=perm,
        tool_context=tool_context,
    )

    task = "请查看 aibes_agent 项目结构，列出所有 Python 文件，并给出这个项目的简要说明。"
    print(f"Task: {task}\n")
    print("=" * 60)

    async for event in agent.run(task):
        if event["type"] == "llm_response":
            print(f"\n[LLM Turn {event['turn']}]\n{event['content']}")
            if event["tool_calls"]:
                print(f"Tool calls: {[tc['function']['name'] for tc in event['tool_calls']]}")
        elif event["type"] == "tool_result":
            print(f"\n[Tool: {event['name']}]\n{event['content'][:500]}")
        elif event["type"] == "error":
            print(f"\n[Error] {event['message']}")
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


if __name__ == "__main__":
    asyncio.run(main())
