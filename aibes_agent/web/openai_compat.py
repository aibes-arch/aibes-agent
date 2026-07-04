"""OpenAI-compatible request/response models and SSE chunk helpers.

Used by the ``/v1/chat/completions`` endpoint so LobeChat and other
OpenAI clients can talk to aibes-agent.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ChatMessage(BaseModel):
    """A single message in an OpenAI chat completion request."""

    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    """OpenAI-compatible chat completion request.

    ``session_id`` is an aibes-agent extension that allows LobeChat to keep a
    multi-turn conversation state on the agent side.
    """

    model: str
    messages: List[ChatMessage]
    stream: bool = False
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    session_id: Optional[str] = Field(default=None, alias="session_id")

    model_config = ConfigDict(populate_by_name=True)


class ChatCompletionUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionChoice(BaseModel):
    index: int = 0
    message: Dict[str, Any]
    finish_reason: Optional[str] = None


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: ChatCompletionUsage


DONE_SENTINEL = "[DONE]"


def _completion_id() -> str:
    return f"chatcmpl-{uuid.uuid4().hex[:24]}"


def _now() -> int:
    return int(time.time())


def make_chunk(
    completion_id: str,
    created: int,
    model: str,
    delta: Dict[str, Any],
    finish_reason: Optional[str] = None,
    usage: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Return an SSE payload dict for one OpenAI-compatible chunk."""
    chunk: Dict[str, Any] = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": delta,
                "finish_reason": finish_reason,
            }
        ],
    }
    if usage is not None:
        chunk["usage"] = usage
    return {"data": json.dumps(chunk, ensure_ascii=False)}


def make_content_chunk(
    completion_id: str,
    created: int,
    model: str,
    content: str,
) -> Dict[str, Any]:
    """Emit a chunk carrying assistant content."""
    return make_chunk(
        completion_id,
        created,
        model,
        {"role": "assistant", "content": content},
        finish_reason=None,
    )


def make_stop_chunk(
    completion_id: str,
    created: int,
    model: str,
    usage: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Emit the final chunk with ``finish_reason="stop"``."""
    return make_chunk(
        completion_id,
        created,
        model,
        {},
        finish_reason="stop",
        usage=usage,
    )


def make_chat_completion_response(
    completion_id: str,
    created: int,
    model: str,
    content: str,
    usage: Optional[Dict[str, Any]] = None,
) -> ChatCompletionResponse:
    """Build a non-streaming OpenAI-compatible response."""
    return ChatCompletionResponse(
        id=completion_id,
        created=created,
        model=model,
        choices=[
            ChatCompletionChoice(
                index=0,
                message={"role": "assistant", "content": content},
                finish_reason="stop",
            )
        ],
        usage=ChatCompletionUsage(**(usage or {})),
    )
