import asyncio
import os

from minagent import (
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
        model=os.getenv("MINAGENT_MODEL", "qwen3-coder-plus-32k"),
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
    tool_context = ToolContext(cwd="/c/aibes/minagent")

    # 6. 运行 Agent
    agent = AgentLoop(
        llm=llm,
        registry=registry,
        config=config,
        permission_engine=perm,
        tool_context=tool_context,
    )

    task = "请查看 minagent 项目结构，列出所有 Python 文件，并给出这个项目的简要说明。"
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
        elif event["type"] == "error":
            print(f"\n[Error] {event['message']}")


if __name__ == "__main__":
    asyncio.run(main())
