from __future__ import annotations

import os
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx
from loguru import logger
from pydantic import BaseModel, Field

from minagent.core.retry import async_retry


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[Dict[str, Any]]
    tools: Optional[List[Dict[str, Any]]] = None
    temperature: float = 0.2
    max_tokens: int = 4000


class LLMClient:
    """OpenAI 兼容的 LLM 客户端。"""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 120.0,
        max_retries: int = 2,
        retry_delay: float = 1.0,
    ):
        self.base_url = (
            base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        ).rstrip("/")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model or os.environ.get("MINAGENT_MODEL", "gpt-4o-mini")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: int = 4000,
        temperature: float = 0.2,
    ) -> "LLMResponse":
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        logger.info(
            "LLM request: url={}/chat/completions model={} timeout={}s",
            self.base_url,
            self.model,
            self.timeout,
        )

        async def _post() -> httpx.Response:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                logger.info("LLM response status: {}", response.status_code)
                response.raise_for_status()
                return response

        try:
            response = await async_retry(
                _post,
                max_retries=self.max_retries,
                delay=self.retry_delay,
                retry_on=(httpx.HTTPError, httpx.NetworkError, TimeoutError),
            )
        except httpx.HTTPStatusError as exc:
            # 超过重试次数后，保留最后一次异常信息
            raise exc

        data = response.json()
        return LLMResponse.from_openai(data)


class LLMResponse:
    """LLM 响应封装。"""

    def __init__(
        self,
        content: str = "",
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        model: str = "",
        usage: Optional[Dict[str, int]] = None,
    ):
        self.content = content
        self.tool_calls = tool_calls or []
        self.model = model
        self.usage = usage or {}

    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0

    def to_message(self) -> Dict[str, Any]:
        message: Dict[str, Any] = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            message["tool_calls"] = self.tool_calls
        return message

    @staticmethod
    def from_openai(data: Dict[str, Any]) -> "LLMResponse":
        choice = data["choices"][0]
        message = choice.get("message", {})
        content = message.get("content") or ""
        tool_calls = message.get("tool_calls", [])
        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            model=data.get("model", ""),
            usage=data.get("usage", {}),
        )
