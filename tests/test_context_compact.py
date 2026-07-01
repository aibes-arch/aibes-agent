import pytest

from aibes_agent.core.context import ContextWindow, Message
from aibes_agent.core.llm import LLMClient, LLMResponse


class FakeLLMClient(LLMClient):
    def __init__(self, response_text: str):
        # 跳过父类 __init__ 中从环境变量读取的逻辑
        self.base_url = "http://fake"
        self.api_key = "fake"
        self.model = "fake"
        self.timeout = 1.0
        self.max_retries = 0
        self.retry_delay = 0.0
        self._response = LLMResponse(content=response_text)

    async def chat(self, messages, tools=None, max_tokens=4000, temperature=0.2):
        return self._response


@pytest.mark.asyncio
async def test_compact_without_llm():
    ctx = ContextWindow()
    for i in range(8):
        ctx.add_user(f"msg{i}")
        ctx.add_assistant(f"reply{i}")

    await ctx.compact()

    assert len(ctx.messages) == 7  # summary + recent 6
    assert ctx.messages[0].content == "[Earlier conversation was compacted]"


@pytest.mark.asyncio
async def test_compact_with_llm_summary():
    ctx = ContextWindow()
    for i in range(8):
        ctx.add_user(f"msg{i}")
        ctx.add_assistant(f"reply{i}")

    fake_llm = FakeLLMClient("previous messages were about testing")
    await ctx.compact(fake_llm)

    assert len(ctx.messages) == 7
    assert "Summary of earlier conversation" in ctx.messages[0].content
    assert "previous messages were about testing" in ctx.messages[0].content


@pytest.mark.asyncio
async def test_compact_fallback_on_llm_error():
    ctx = ContextWindow()
    for i in range(8):
        ctx.add_user(f"msg{i}")
        ctx.add_assistant(f"reply{i}")

    class BadLLM(LLMClient):
        def __init__(self):
            self.base_url = "http://fake"
            self.api_key = "fake"
            self.model = "fake"
            self.timeout = 1.0
            self.max_retries = 0
            self.retry_delay = 0.0

        async def chat(self, *args, **kwargs):
            raise RuntimeError("boom")

    await ctx.compact(BadLLM())
    assert "Earlier conversation was compacted" in ctx.messages[0].content
