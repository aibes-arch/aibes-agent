"""v0.4.0 文档处理 Agent 演示。

本示例展示如何使用文档处理领域工具（PdfExtract、MarkdownMerge）
提取 PDF 内容或合并 Markdown 文件。
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
    FileReadTool,
    GlobTool,
    LLMClient,
    MarkdownMergeTool,
    PdfExtractTool,
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

    registry = ToolRegistry()
    registry.register_many(
        [
            FileReadTool(),
            BashTool(),
            GlobTool(),
            PdfExtractTool(),
            MarkdownMergeTool(),
        ]
    )

    config = AgentConfig(
        system_prompt="""你是一位文档处理助手。你可以帮助用户：
1. 使用 PdfExtract 从 PDF 文件中提取文本。
2. 使用 MarkdownMerge 合并多个 Markdown 文件。
3. 对提取的内容进行摘要、整理或回答具体问题。

请优先使用工具读取文件，然后给出结构化的回答。""",
        max_turns=15,
    )

    perm = PermissionEngine(
        rules=[
            PermissionRule("allow", "tool", "FileRead"),
            PermissionRule("allow", "tool", "Glob"),
            PermissionRule("allow", "tool", "Bash"),
            PermissionRule("allow", "tool", "PdfExtract"),
            PermissionRule("allow", "tool", "MarkdownMerge"),
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
        "请查找当前项目中可处理的文档（PDF 或 Markdown），" "提取或合并相关内容，并给出简要摘要。"
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
            print(f"\n{'='*60}\n[文档处理结果]\n{event['content']}")
        elif event["type"] == "error":
            print(f"\n[Error] {event['message']}")


if __name__ == "__main__":
    asyncio.run(main())
