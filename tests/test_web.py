import asyncio

import pytest
from fastapi.testclient import TestClient

from aibes_agent.config import MinagentConfig
from aibes_agent.core.engine import AgentConfig
from aibes_agent.core.llm import LLMClient
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
        assert "aibes_agent Web UI" in response.text


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
        events.append(payload)
    await task

    assert len(events) == 1
    assert events[0]["event"] == "llm_response"
    assert events[0]["data"]["turn"] == 1
