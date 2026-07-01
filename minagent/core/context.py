from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from minagent.core.llm import LLMClient


class Message(BaseModel):
    role: str
    content: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None

    def to_openai(self) -> Dict[str, Any]:
        msg: Dict[str, Any] = {"role": self.role}
        if self.content is not None:
            msg["content"] = self.content
        if self.tool_calls is not None:
            msg["tool_calls"] = self.tool_calls
        if self.tool_call_id is not None:
            msg["tool_call_id"] = self.tool_call_id
        if self.name is not None:
            msg["name"] = self.name
        return msg


class ContextWindow(BaseModel):
    """上下文窗口管理。"""

    max_tokens: int = Field(default=128000, ge=1000)
    messages: List[Message] = Field(default_factory=list)

    def add(self, message: Message) -> None:
        self.messages.append(message)

    def add_user(self, content: str) -> None:
        self.add(Message(role="user", content=content))

    def add_assistant(
        self, content: str, tool_calls: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        self.add(Message(role="assistant", content=content, tool_calls=tool_calls))

    def add_tool_result(self, tool_call_id: str, content: str, name: str) -> None:
        self.add(Message(role="tool", content=content, tool_call_id=tool_call_id, name=name))

    def to_openai_messages(self) -> List[Dict[str, Any]]:
        return [msg.to_openai() for msg in self.messages]

    def rough_token_count(self) -> int:
        """粗略估算 token 数。"""
        total = 0
        for msg in self.messages:
            text = msg.content or ""
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    text += str(tc.get("function", {}).get("arguments", ""))
            total += len(text) // 4
        return total

    def should_compact(self) -> bool:
        return self.rough_token_count() > self.max_tokens * 0.8

    @staticmethod
    def _format_for_summary(messages: List[Message]) -> str:
        """把消息列表格式化为用于摘要的文本。"""
        lines = []
        for msg in messages:
            role = msg.role
            content = msg.content or ""
            if msg.tool_calls:
                names = [tc.get("function", {}).get("name", "unknown") for tc in msg.tool_calls]
                content = f"[tool_calls: {', '.join(names)}]\n{content}"
            lines.append(f"[{role}] {content}")
        return "\n".join(lines)

    async def compact(self, llm: Optional[LLMClient] = None) -> None:
        """压缩上下文。

        如果提供了 ``llm``，则使用 LLM 生成被丢弃消息的摘要；
        否则使用简单的占位提示。
        """
        if len(self.messages) <= 6:
            return

        system_msgs = [m for m in self.messages if m.role == "system"]
        recent = self.messages[-6:]
        middle = self.messages[len(system_msgs) : -6]

        if not middle:
            self.messages = system_msgs + recent
            return

        summary_text = "[Earlier conversation was compacted]"

        if llm is not None:
            try:
                conversation_text = self._format_for_summary(middle)
                summary_prompt = (
                    "Summarize the following conversation history into a concise "
                    "paragraph. Keep key facts, decisions, and tool results that "
                    "are still relevant to the user's task.\n\n"
                    f"{conversation_text}"
                )
                response = await llm.chat(
                    messages=[
                        {"role": "system", "content": "You are a helpful summarizer."},
                        {"role": "user", "content": summary_prompt},
                    ],
                    max_tokens=500,
                    temperature=0.2,
                )
                summary = response.content.strip()
                if summary:
                    summary_text = f"[Summary of earlier conversation: {summary}]"
            except Exception:
                # LLM 摘要失败时回退到占位提示
                pass

        self.messages = system_msgs + [Message(role="user", content=summary_text)] + recent
