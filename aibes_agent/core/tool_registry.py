from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from aibes_agent.core.retry import async_retry
from aibes_agent.tools.base import Tool, ToolContext, ToolResult


class ToolRegistry:
    """工具注册表。"""

    def __init__(
        self,
        max_tool_retries: int = 2,
        tool_retry_delay: float = 1.0,
    ) -> None:
        self._tools: Dict[str, Tool] = {}
        self.max_tool_retries = max_tool_retries
        self.tool_retry_delay = tool_retry_delay

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
            try:
                tool = self.get_tool(tc["function"]["name"])
            except ValueError:
                # Unknown tool will be reported as an error during execution
                batches.append({"is_concurrent": False, "calls": [tc], "error": "Tool not found"})
                continue

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
        results = []
        batches = self._partition_tool_calls(tool_calls)
        for batch in batches:
            if batch.get("error"):
                for tc in batch["calls"]:
                    results.append(
                        {
                            "tool_call_id": tc["id"],
                            "role": "tool",
                            "name": tc["function"]["name"],
                            "content": f"Error: {batch['error']}",
                        }
                    )
                continue

            if batch["is_concurrent"]:
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
                        assert isinstance(res, dict)
                        results.append(res)
            else:
                for tc in batch["calls"]:
                    try:
                        res = await self._execute_single(tc, context)
                        results.append(res)
                    except Exception as exc:
                        results.append(
                            {
                                "tool_call_id": tc["id"],
                                "role": "tool",
                                "name": tc["function"]["name"],
                                "content": f"Error: {exc}",
                            }
                        )
        return results

    @staticmethod
    def _result_to_dict(
        tool_call_id: str,
        tool_name: str,
        result: ToolResult,
    ) -> Dict[str, Any]:
        content = result.content
        if result.error:
            content = f"{content}\nError: {result.error}".strip()
        return {
            "tool_call_id": tool_call_id,
            "role": "tool",
            "name": tool_name,
            "content": content,
        }

    async def _execute_single(
        self, tool_call: Dict[str, Any], context: ToolContext
    ) -> Dict[str, Any]:
        tool_name = tool_call["function"]["name"]
        tool = self.get_tool(tool_name)
        input_model = tool.input_model
        tool_call_id = tool_call["id"]

        try:
            raw_args = tool_call["function"].get("arguments", {})
            if isinstance(raw_args, str):
                raw_args = json.loads(raw_args)
            parsed = input_model.model_validate(raw_args)
        except Exception as e:
            return {
                "tool_call_id": tool_call_id,
                "role": "tool",
                "name": tool_name,
                "content": f"Input validation error: {e}",
            }

        read_only = tool.is_read_only(parsed)

        # 只读工具优先查缓存
        cache_key: Optional[str] = None
        if read_only and context.cache is not None:
            cache_key = context.cache.make_key(tool_name, raw_args, context.cwd)
            cached = context.cache.get(cache_key)
            if cached is not None:
                return self._result_to_dict(tool_call_id, tool_name, cached)

        async def _invoke() -> ToolResult:
            return await tool.call(parsed, context)

        try:
            if read_only and self.max_tool_retries > 0:
                result = await async_retry(
                    _invoke,
                    max_retries=self.max_tool_retries,
                    delay=self.tool_retry_delay,
                    retry_on=(Exception,),
                )
            else:
                result = await _invoke()
        except Exception as e:
            result = ToolResult.fail(f"Execution error: {e}")

        # 只读工具写入缓存
        if read_only and context.cache is not None and cache_key is not None:
            context.cache.set(cache_key, result)

        return self._result_to_dict(tool_call_id, tool_name, result)
