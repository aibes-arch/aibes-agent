from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, Generic, Optional, Type, TypeVar

from pydantic import BaseModel

if TYPE_CHECKING:
    from minagent.core.cache import ToolResultCache

InputT = TypeVar("InputT", bound=BaseModel)


@dataclass
class ToolContext:
    """工具执行上下文。"""

    cwd: str
    env: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    cache: Optional["ToolResultCache"] = None

    def get(self, key: str, default: Any = None) -> Any:
        return self.metadata.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.metadata[key] = value


@dataclass
class ToolResult:
    """工具执行结果。"""

    success: bool
    content: str
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def ok(content: str, **metadata) -> "ToolResult":
        return ToolResult(success=True, content=content, metadata=metadata)

    @staticmethod
    def fail(error: str, content: str = "", **metadata) -> "ToolResult":
        return ToolResult(success=False, content=content, error=error, metadata=metadata)


class Tool(ABC, Generic[InputT]):
    """工具基类。"""

    name: str = ""
    description: str = ""
    input_model: Type[InputT]
    output_model: Type[Any] = ToolResult

    def __init__(self) -> None:
        if not self.name:
            raise ValueError("Tool subclass must define 'name'")
        if not self.description:
            raise ValueError("Tool subclass must define 'description'")

    def to_openai_schema(self) -> Dict[str, Any]:
        """转换为 OpenAI function schema。"""
        schema = self.input_model.model_json_schema()
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": schema,
            },
        }

    def is_read_only(self, input: InputT) -> bool:
        """是否为只读工具，用于并发控制。"""
        return False

    def is_concurrency_safe(self, input: InputT) -> bool:
        """是否可以并发执行。"""
        return self.is_read_only(input)

    @abstractmethod
    async def call(self, input: InputT, context: ToolContext) -> ToolResult:
        """执行工具。"""
        pass
