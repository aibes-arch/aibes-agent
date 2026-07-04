import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from aibes_agent.config import MinagentConfig
from aibes_agent.core.engine import AgentConfig
from aibes_agent.core.llm import LLMClient, LLMResponse
from aibes_agent.core.session import FileSessionStore
from aibes_agent.core.tool_registry import ToolRegistry
from aibes_agent.permissions.engine import PermissionEngine
from aibes_agent.tools import FileReadTool
from aibes_agent.tools.base import ToolContext
from aibes_agent.web.runner import WebRunner
from aibes_agent.web.server import create_app


@pytest.fixture
def app_config(tmp_path):
    cfg = MinagentConfig()
    cfg.session.path = str(tmp_path / "sessions")
    return cfg


def test_web_index(app_config):
    app = create_app(app_config)
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "aibes_agent · Agent Chat" in response.text


def test_web_tools_endpoint(app_config):
    app = create_app(app_config)
    with TestClient(app) as client:
        response = client.get("/api/tools")
        assert response.status_code == 200
        assert "FileRead" in response.json()["tools"]


def test_web_sessions_endpoint(app_config):
    app = create_app(app_config)
    with TestClient(app) as client:
        response = client.get("/api/sessions")
        assert response.status_code == 200
        assert response.json()["sessions"] == []


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


def test_chat_completions_non_stream(app_config):
    app = create_app(app_config)

    with TestClient(app) as client:
        client.app.state.runner.llm = MockLLM([LLMResponse(content="Hello from agent", tool_calls=[])])
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "test",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": False,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "chat.completion"
        assert data["model"] == "test"
        assert data["choices"][0]["message"]["role"] == "assistant"
        assert data["choices"][0]["message"]["content"] == "Hello from agent"
        assert data["choices"][0]["finish_reason"] == "stop"
        assert "usage" in data


def test_chat_completions_stream(app_config):
    app = create_app(app_config)

    with TestClient(app) as client:
        client.app.state.runner.llm = MockLLM([LLMResponse(content="Hello from agent", tool_calls=[])])
        with client.stream(
            "POST",
            "/v1/chat/completions",
            json={
                "model": "test",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": True,
            },
        ) as response:
            assert response.status_code == 200
            lines = [line for line in response.iter_lines() if line.startswith("data:")]
            assert len(lines) >= 2
            assert lines[-1] == "data: [DONE]"

            content_chunk = json.loads(lines[0][5:].strip())
            assert content_chunk["object"] == "chat.completion.chunk"
            assert content_chunk["choices"][0]["delta"]["content"] == "Hello from agent"

            stop_chunk = json.loads(lines[-2][5:].strip())
            assert stop_chunk["choices"][0]["finish_reason"] == "stop"


@pytest.mark.asyncio
async def test_runner_event_stream(tmp_path):
    registry = ToolRegistry()
    registry.register(FileReadTool())
    runner = WebRunner(
        registry=registry,
        agent_config=AgentConfig(),
        llm=LLMClient(base_url="http://localhost/v1", model="test"),
        permission_engine=PermissionEngine.default(),
        model_router=None,
        session_store=FileSessionStore(str(tmp_path / "sessions")),
        tool_context=ToolContext(cwd="/"),
    )

    async def producer():
        await asyncio.sleep(0.05)
        await runner._broadcast("s1", {"type": "llm_response", "turn": 1})
        await runner._broadcast("s1", None)

    task = asyncio.create_task(producer())
    events = []
    async for payload in runner.event_stream("s1"):
        events.append(json.loads(payload["data"]))
    await task

    assert len(events) == 1
    assert events[0]["type"] == "llm_response"
    assert events[0]["turn"] == 1
