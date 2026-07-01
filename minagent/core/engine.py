from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator, Dict, List, Optional

from minagent.core.context import ContextWindow, Message
from minagent.core.llm import LLMClient, LLMResponse
from minagent.core.tool_registry import ToolRegistry
from minagent.permissions.engine import PermissionEngine
from minagent.tools.base import ToolContext


class AgentConfig:
    """Agent 配置。"""

    def __init__(
        self,
        system_prompt: str = "",
        max_turns: int = 30,
        max_tokens_per_turn: int = 4000,
        temperature: float = 0.2,
        auto_compact: bool = True,
    ):
        self.system_prompt = system_prompt
        self.max_turns = max_turns
        self.max_tokens_per_turn = max_tokens_per_turn
        self.temperature = temperature
        self.auto_compact = auto_compact


class AgentLoop:
    """Agent 主循环。"""

    def __init__(
        self,
        llm: LLMClient,
        registry: ToolRegistry,
        config: AgentConfig,
        permission_engine: Optional[PermissionEngine] = None,
        tool_context: Optional[ToolContext] = None,
    ):
        self.llm = llm
        self.registry = registry
        self.config = config
        self.permission_engine = permission_engine or PermissionEngine()
        self.tool_context = tool_context or ToolContext(cwd="/")

    async def run(
        self,
        task: str,
        initial_context: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """运行 Agent 循环，产生事件。"""
        ctx = ContextWindow()
        if self.config.system_prompt:
            ctx.add(Message(role="system", content=self.config.system_prompt))
        ctx.add_user(task)

        yield {"type": "user_task", "content": task}

        for turn in range(self.config.max_turns):
            if self.config.auto_compact and ctx.should_compact():
                ctx.compact()
                yield {"type": "compact", "message": "Context compacted"}

            tools = self.registry.to_openai_schemas()
            response = await self.llm.chat(
                messages=ctx.to_openai_messages(),
                tools=tools,
                max_tokens=self.config.max_tokens_per_turn,
                temperature=self.config.temperature,
            )

            yield {
                "type": "llm_response",
                "turn": turn + 1,
                "content": response.content,
                "tool_calls": response.tool_calls,
                "model": response.model,
                "usage": response.usage,
            }

            ctx.add_assistant(response.content, response.tool_calls)

            if not response.has_tool_calls():
                yield {"type": "final", "content": response.content}
                return

            # 权限检查
            allowed_tool_calls = []
            for tc in response.tool_calls:
                tool_name = tc["function"]["name"]
                arguments = tc["function"].get("arguments", {})
                permitted = await self.permission_engine.check(
                    tool_name, arguments, self.tool_context
                )
                if permitted:
                    allowed_tool_calls.append(tc)
                else:
                    yield {
                        "type": "permission_denied",
                        "tool_call": tc,
                        "reason": "Permission denied",
                    }
                    ctx.add_tool_result(
                        tc["id"],
                        f"Permission denied: tool '{tool_name}' was not allowed.",
                        tool_name,
                    )

            if not allowed_tool_calls:
                yield {"type": "error", "message": "All tool calls were denied"}
                return

            # 执行工具
            tool_results = await self.registry.execute(allowed_tool_calls, self.tool_context)

            for tr in tool_results:
                yield {
                    "type": "tool_result",
                    "tool_call_id": tr["tool_call_id"],
                    "name": tr["name"],
                    "content": tr["content"],
                }
                ctx.add_tool_result(tr["tool_call_id"], tr["content"], tr["name"])

        yield {
            "type": "error",
            "message": f"Reached max turns ({self.config.max_turns})",
        }
