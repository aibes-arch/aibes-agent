from __future__ import annotations

from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel

from minagent.tools.base import Tool, ToolContext, ToolResult


class ToolRegistry:
    """工具注册表。"""

    def __init__(self) -> None:
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> "ToolRegistry":
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' already registered")
        self._tools[tool.name] = tool
        return self

    def register_many(self, tools: List[Tool]) -> "ToolRegistry":
        for tool in tools:
            self.register(tool)
        return self

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def has(self, name: str) -> bool:
        return name in self._tools

    def list_tools(self) -> List[str]:
        return list(self._tools.keys())

    def to_openai_schemas(self) -> List[Dict[str, Any]]:
        return [tool.to_openai_schema() for tool in self._tools.values()]

    def get_tool(self, name: str) -> Tool:
        tool = self.get(name)
        if tool is None:
            raise ValueError(f"Tool '{name}' not found")
        return tool

    def _partition_tool_calls(self, tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """将 tool_calls 分成可并发和需串行的批次。"""
        batches: List[Dict[str, Any]] = []
        for tc in tool_calls:
            tool = self.get_tool(tc["function"]["name"])
            input_model = tool.input_model
            try:
                parsed = input_model.model_validate(tc["function"].get("arguments", {}))
                is_concurrent = tool.is_concurrency_safe(parsed)
            except Exception:
                is_concurrent = False

            if is_concurrent and batches and batches[-1].get("is_concurrent"):
                batches[-1]["calls"].append(tc)
            else:
                batches.append({"is_concurrent": is_concurrent, "calls": [tc]})
        return batches

    async def execute(
        self,
        tool_calls: List[Dict[str, Any]],
        context: ToolContext,
    ) -> List[Dict[str, Any]]:
        """执行一组 tool_calls，返回 tool_results。"""
        import asyncio

        results = []
        batches = self._partition_tool_calls(tool_calls)
        for batch in batches:
            if batch["is_concurrent"]:
                # 并发执行
                coros = []
                for tc in batch["calls"]:
                    coros.append(self._execute_single(tc, context))
                batch_results = await asyncio.gather(*coros, return_exceptions=True)
                for tc, res in zip(batch["calls"], batch_results):
                    if isinstance(res, Exception):
                        results.append(
                            {
                                "tool_call_id": tc["id"],
                                "role": "tool",
                                "name": tc["function"]["name"],
                                "content": f"Error: {res}",
                            }
                        )
                    else:
                        results.append(res)
            else:
                # 串行执行
                for tc in batch["calls"]:
                    res = await self._execute_single(tc, context)
                    results.append(res)
        return results

    async def _execute_single(
        self, tool_call: Dict[str, Any], context: ToolContext
    ) -> Dict[str, Any]:
        tool_name = tool_call["function"]["name"]
        tool = self.get_tool(tool_name)
        input_model = tool.input_model

        try:
            raw_args = tool_call["function"].get("arguments", {})
            if isinstance(raw_args, str):
                import json

                raw_args = json.loads(raw_args)
            parsed = input_model.model_validate(raw_args)
        except Exception as e:
            return {
                "tool_call_id": tool_call["id"],
                "role": "tool",
                "name": tool_name,
                "content": f"Input validation error: {e}",
            }

        try:
            result = await tool.call(parsed, context)
            content = result.content
            if result.error:
                content = f"{content}\nError: {result.error}".strip()
            return {
                "tool_call_id": tool_call["id"],
                "role": "tool",
                "name": tool_name,
                "content": content,
            }
        except Exception as e:
            return {
                "tool_call_id": tool_call["id"],
                "role": "tool",
                "name": tool_name,
                "content": f"Execution error: {e}",
            }
