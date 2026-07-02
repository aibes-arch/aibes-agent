"""v0.4.0 钻井工程代码分析 Agent 演示。

本示例展示如何使用钻井领域工具（ParseWitsml、AnalyzeDrillingLog、ValidateFormula、QueryKnowledgeBase）
分析钻井数据、验证水力学公式并查询行业知识库。
"""

import asyncio
import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from aibes_agent import (
    AgentConfig,
    AgentLoop,
    AnalyzeDrillingLogTool,
    BashTool,
    FileReadTool,
    GlobTool,
    GrepTool,
    LLMClient,
    ParseWitsmlTool,
    PermissionEngine,
    PermissionRule,
    QueryKnowledgeBaseTool,
    TaskListTool,
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
            GrepTool(),
            GlobTool(),
            TaskListTool(),
            ParseWitsmlTool(),
            AnalyzeDrillingLogTool(),
            ValidateFormulaTool(),
            QueryKnowledgeBaseTool(),
        ]
    )

    config = AgentConfig(
        system_prompt="""你是一位钻井工程分析专家。你可以帮助用户：
1. 使用 ParseWitsml 解析 WITSML 文件，提取井名、测深、曲线等信息。
2. 使用 AnalyzeDrillingLog 分析钻井日志（CSV/JSON），检测 ROP、WOB、RPM 等参数的异常。
3. 使用 ValidateFormula 验证水力学公式（如 ECD、环空压耗）和单位换算。
4. 使用 QueryKnowledgeBase 查询钻井规程、最佳实践和事故案例。

请结合数据给出专业、严谨的分析结论，并标注安全相关事项。""",
        max_turns=15,
    )

    perm = PermissionEngine(
        rules=[
            PermissionRule("allow", "tool", "FileRead"),
            PermissionRule("allow", "tool", "Grep"),
            PermissionRule("allow", "tool", "Glob"),
            PermissionRule("allow", "tool", "Bash"),
            PermissionRule("allow", "tool", "TaskList"),
            PermissionRule("allow", "tool", "ParseWitsml"),
            PermissionRule("allow", "tool", "AnalyzeDrillingLog"),
            PermissionRule("allow", "tool", "ValidateFormula"),
            PermissionRule("allow", "tool", "QueryKnowledgeBase"),
            PermissionRule("allow", "shell", "git .*"),
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

    task = (
        "请分析当前项目中的钻井相关数据文件（如有 WITSML、CSV 日志等），"
        "验证一个常见水力学公式，并查询相关知识库给出安全建议。"
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
            print(f"\n{'='*60}\n[分析报告]\n{event['content']}")
        elif event["type"] == "error":
            print(f"\n[Error] {event['message']}")


if __name__ == "__main__":
    asyncio.run(main())
