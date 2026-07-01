import pytest

from minagent import AgentProfile, AgentTool, FileReadTool
from minagent.core.llm import LLMClient, LLMResponse
from minagent.tools.base import ToolContext


class FakeLLMClient(LLMClient):
    """返回固定响应的 LLMClient，用于测试子 Agent。"""

    def __init__(self, response: LLMResponse):
        self.base_url = "http://fake"
        self.api_key = "fake"
        self.model = "fake-model"
        self.timeout = 1.0
        self.max_retries = 0
        self.retry_delay = 0.0
        self._response = response

    async def chat(self, messages, tools=None, max_tokens=4000, temperature=0.2):
        return self._response


@pytest.fixture
def tool_pool(tmp_path):
    return {"FileRead": FileReadTool()}


@pytest.mark.asyncio
async def test_agent_tool_unknown_profile(tool_pool):
    tool = AgentTool(
        profiles={"default": AgentProfile(name="default")},
        llm=FakeLLMClient(LLMResponse(content="done")),
        tool_pool=tool_pool,
    )
    result = await tool.call(
        tool.input_model(task="do something", agent_profile="missing"),
        ToolContext(cwd="/tmp"),
    )
    assert not result.success
    assert "not found" in (result.content or result.error or "")


@pytest.mark.asyncio
async def test_agent_tool_runs_sub_agent(tool_pool, tmp_path):
    # 准备一个文件，子 Agent 会读取
    sample = tmp_path / "sample.txt"
    sample.write_text("project summary here", encoding="utf-8")

    llm = FakeLLMClient(
        LLMResponse(
            content="",
            tool_calls=[
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "FileRead",
                        "arguments": {"file_path": str(sample)},
                    },
                }
            ],
        )
    )

    tool = AgentTool(
        profiles={
            "default": AgentProfile(
                name="default",
                system_prompt="Read the sample file and summarize.",
                tools=["FileRead"],
                max_turns=3,
            )
        },
        llm=llm,
        tool_pool=tool_pool,
    )

    # 第二轮 LLM 返回最终答案
    final_llm = FakeLLMClient(LLMResponse(content="final summary from sub-agent"))

    # 让 tool 在第二轮使用 final_llm：把 tool_pool 中的 FileRead 保留，但更换 llm 不可行，
    # 因为 AgentTool 使用 self.llm。这里通过构造一个会切换响应的 fake LLM。
    class TwoStepLLM(LLMClient):
        def __init__(self):
            self.base_url = "http://fake"
            self.api_key = "fake"
            self.model = "fake"
            self.timeout = 1.0
            self.max_retries = 0
            self.retry_delay = 0.0
            self.step = 0

        async def chat(self, messages, tools=None, max_tokens=4000, temperature=0.2):
            self.step += 1
            if self.step == 1:
                return LLMResponse(
                    content="",
                    tool_calls=[
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "FileRead",
                                "arguments": {"file_path": str(sample)},
                            },
                        }
                    ],
                )
            return LLMResponse(content="final summary from sub-agent")

    tool = AgentTool(
        profiles={
            "default": AgentProfile(
                name="default",
                system_prompt="Read the sample file and summarize.",
                tools=["FileRead"],
                max_turns=3,
            )
        },
        llm=TwoStepLLM(),
        tool_pool=tool_pool,
    )

    ctx = ToolContext(cwd=str(tmp_path))
    result = await tool.call(tool.input_model(task="summarize"), ctx)
    assert result.success
    assert "final summary from sub-agent" in result.content
    assert result.metadata.get("turns", 0) >= 1
