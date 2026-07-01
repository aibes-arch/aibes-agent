"""Agent 运行统计。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class RunStats:
    """记录一次 Agent 运行的关键指标。"""

    turn_count: int = 0
    llm_call_count: int = 0
    tool_call_count: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    errors: List[str] = field(default_factory=list)

    def update_from_usage(self, usage: Dict[str, int]) -> None:
        """根据 LLM 返回的 usage 更新 token 统计。"""
        self.total_prompt_tokens += usage.get("prompt_tokens", 0)
        self.total_completion_tokens += usage.get("completion_tokens", 0)
        self.total_tokens += usage.get("total_tokens", 0)

    def add_error(self, message: str) -> None:
        """记录一次错误。"""
        self.errors.append(message)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn_count": self.turn_count,
            "llm_call_count": self.llm_call_count,
            "tool_call_count": self.tool_call_count,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_tokens,
            "errors": self.errors,
        }
