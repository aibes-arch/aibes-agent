"""v0.4.0 代码审查 Agent 演示。

本示例使用新的代码审查领域工具（GitDiff、Lint、Coverage）自动审查当前 git 工作区的变更。
"""

import asyncio
import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from aibes_agent import (
    AgentConfig,
    AgentLoop,
    BashTool,
    CoverageTool,
    FileReadTool,
    GitDiffTool,
    GlobTool,
    GrepTool,
    LintTool,
    LLMClient,
    PermissionEngine,
    PermissionRule,
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

    registry = ToolRegistry()
    registry.register_many(
        [
            FileReadTool(),
            BashTool(),
            GrepTool(),
            GlobTool(),
            TaskListTool(),
            GitDiffTool(),
            LintTool(),
            CoverageTool(),
        ]
    )

    config = AgentConfig(
        system_prompt="""你是一位严格的代码审查专家。请按以下维度审查代码变更：
1. 正确性：是否有明显 bug、异常处理是否完整
2. 可维护性：命名、注释、复杂度、重复代码
3. 安全性：是否有 SQL 注入、命令注入、敏感信息泄露
4. 性能：是否有不必要的循环、阻塞操作
5. 测试覆盖：新增代码是否有对应测试

请优先使用 GitDiff 获取变更，使用 Lint 运行静态检查，使用 Coverage 查看测试覆盖率，
最终输出一份结构化的 Markdown 审查报告。""",
        max_turns=15,
    )

    perm = PermissionEngine(
        rules=[
            PermissionRule("allow", "tool", "FileRead"),
            PermissionRule("allow", "tool", "Grep"),
            PermissionRule("allow", "tool", "Glob"),
            PermissionRule("allow", "tool", "Bash"),
            PermissionRule("allow", "tool", "TaskList"),
            PermissionRule("allow", "tool", "GitDiff"),
            PermissionRule("allow", "tool", "Lint"),
            PermissionRule("allow", "tool", "Coverage"),
            PermissionRule("allow", "shell", "git .*"),
            PermissionRule("allow", "shell", "pytest .*"),
            PermissionRule("allow", "shell", "ruff .*"),
            PermissionRule("allow", "shell", "python -m pytest .*"),
        ],
        mode="auto",
    )

    tool_context = ToolContext(cwd=os.getcwd())

    agent = AgentLoop(
        llm=llm,
        registry=registry,
        config=config,
        permission_engine=perm,
        tool_context=tool_context,
    )

    task = "请审查当前 git 工作区的代码变更，输出一份代码审查报告。"

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
            print(f"\n{'='*60}\n[审查报告]\n{event['content']}")
        elif event["type"] == "error":
            print(f"\n[Error] {event['message']}")


if __name__ == "__main__":
    asyncio.run(main())
