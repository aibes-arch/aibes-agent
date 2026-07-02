import pytest

from aibes_agent import AgentConfig, AgentLoop, BashTool, FileReadTool, ToolRegistry
from aibes_agent.core.llm import LLMClient, LLMResponse
from aibes_agent.permissions.engine import PermissionEngine, PermissionRule
from aibes_agent.tools.base import ToolContext


class MockLLM(LLMClient):
    """A fake LLM that returns scripted responses."""

    def __init__(self, responses):
        super().__init__(base_url="http://mock", api_key="mock", model="mock")
        self.responses = responses
        self.index = 0

    async def chat(self, messages, tools=None, max_tokens=4000, temperature=0.2):
        response = self.responses[self.index]
        self.index += 1
        return response


@pytest.fixture
def registry():
    reg = ToolRegistry()
    reg.register(FileReadTool())
    reg.register(BashTool())
    return reg


@pytest.mark.asyncio
async def test_agent_loop_final_response(registry):
    llm = MockLLM([LLMResponse(content="Final answer", tool_calls=[])])
    config = AgentConfig(system_prompt="You are a test agent.", max_turns=5)
    agent = AgentLoop(llm=llm, registry=registry, config=config)

    events = [e async for e in agent.run("test task")]
    types = [e["type"] for e in events]

    assert types == ["user_task", "llm_response", "final"]
    assert events[-1]["content"] == "Final answer"


@pytest.mark.asyncio
async def test_agent_loop_tool_call_and_final(registry, tmp_path):
    test_file = tmp_path / "hello.txt"
    test_file.write_text("world", encoding="utf-8")

    llm = MockLLM(
        [
            LLMResponse(
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "FileRead",
                            "arguments": {"file_path": str(test_file)},
                        },
                    }
                ],
            ),
            LLMResponse(content="Done", tool_calls=[]),
        ]
    )

    config = AgentConfig(system_prompt="You are a test agent.", max_turns=5)
    perm = PermissionEngine(
        rules=[],
        mode="full_auto",
    )
    agent = AgentLoop(
        llm=llm,
        registry=registry,
        config=config,
        permission_engine=perm,
        tool_context=ToolContext(cwd=str(tmp_path)),
    )

    events = [e async for e in agent.run("read file")]
    types = [e["type"] for e in events]

    assert "user_task" in types
    assert "llm_response" in types
    assert "tool_result" in types
    assert "final" in types


@pytest.mark.asyncio
async def test_agent_loop_permission_denied(registry):
    llm = MockLLM(
        [
            LLMResponse(
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "Bash",
                            "arguments": {"command": "rm -rf /"},
                        },
                    }
                ],
            ),
        ]
    )

    config = AgentConfig(system_prompt="You are a test agent.", max_turns=5)
    perm = PermissionEngine(
        rules=[PermissionRule("deny", "tool", "Bash")],
        mode="auto",
    )
    agent = AgentLoop(
        llm=llm,
        registry=registry,
        config=config,
        permission_engine=perm,
    )

    events = [e async for e in agent.run("dangerous task")]
    types = [e["type"] for e in events]

    assert "permission_denied" in types
    assert "error" in types


@pytest.mark.asyncio
async def test_agent_loop_llm_error(registry):
    class FailingLLM(LLMClient):
        async def chat(self, messages, tools=None, max_tokens=4000, temperature=0.2):
            raise RuntimeError("mock llm failure")

    config = AgentConfig(system_prompt="You are a test agent.", max_turns=5)
    agent = AgentLoop(llm=FailingLLM(), registry=registry, config=config)

    events = [e async for e in agent.run("task")]
    types = [e["type"] for e in events]

    assert "error" in types
    assert "mock llm failure" in events[-1]["message"]


@pytest.mark.asyncio
async def test_agent_loop_max_turns(registry):
    # LLM always requests a tool call, never returns final
    llm = MockLLM(
        [
            LLMResponse(
                content="",
                tool_calls=[
                    {
                        "id": f"call_{i}",
                        "type": "function",
                        "function": {
                            "name": "FileRead",
                            "arguments": {"file_path": "/no/such/file"},
                        },
                    }
                ],
            )
            for i in range(5)
        ]
    )

    config = AgentConfig(system_prompt="You are a test agent.", max_turns=2)
    perm = PermissionEngine(rules=[], mode="full_auto")
    agent = AgentLoop(
        llm=llm,
        registry=registry,
        config=config,
        permission_engine=perm,
    )

    events = [e async for e in agent.run("loop forever")]
    types = [e["type"] for e in events]

    assert "error" in types
    assert "max turns" in events[-1]["message"].lower()
