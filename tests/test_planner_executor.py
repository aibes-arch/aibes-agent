"""Tests for the PlanExecutor."""

from __future__ import annotations

import pytest

from aibes_agent.core.llm import LLMClient
from aibes_agent.core.tool_registry import ToolRegistry
from aibes_agent.planner import Plan, PlanExecutor, Planner
from aibes_agent.planner.models import PlanStep
from aibes_agent.tools import FileReadTool


@pytest.fixture
def client():
    return LLMClient(base_url="http://test", api_key="key", model="test-model", max_retries=0)


@pytest.fixture
def registry():
    reg = ToolRegistry()
    reg.register(FileReadTool())
    return reg


@pytest.mark.asyncio
async def test_executor_runs_steps_in_order(client, registry, httpx_mock):
    httpx_mock.add_response(
        url="http://test/chat/completions",
        json={"choices": [{"message": {"content": "Step 1 done", "tool_calls": []}}]},
    )
    httpx_mock.add_response(
        url="http://test/chat/completions",
        json={"choices": [{"message": {"content": "Step 2 done", "tool_calls": []}}]},
    )

    plan = Plan(
        task="T",
        steps=[
            PlanStep(step_id="1", description="First"),
            PlanStep(step_id="2", description="Second", depends_on=["1"]),
        ],
    )
    executor = PlanExecutor(llm=client, registry=registry)
    result = await executor.execute(plan)

    assert result.steps[0].status == "done"
    assert result.steps[0].result == "Step 1 done"
    assert result.steps[1].status == "done"
    assert result.steps[1].result == "Step 2 done"


@pytest.mark.asyncio
async def test_executor_skips_failed_dependency(client, registry, httpx_mock):
    plan = Plan(
        task="T",
        steps=[
            PlanStep(step_id="1", description="First"),
            PlanStep(step_id="2", description="Second", depends_on=["1"]),
        ],
    )
    executor = PlanExecutor(llm=client, registry=registry)

    # Force step 1 to fail.
    original_run_step = executor._run_step

    async def failing_run_step(step):
        if step.step_id == "1":
            raise RuntimeError("boom")
        return await original_run_step(step)

    executor._run_step = failing_run_step  # type: ignore

    result = await executor.execute(plan)
    assert result.steps[0].status == "failed"
    assert result.steps[1].status == "failed"
    assert "dependency failed" in result.steps[1].result.lower()


@pytest.mark.asyncio
async def test_executor_uses_agent_profile(client, registry, httpx_mock):
    httpx_mock.add_response(
        url="http://test/chat/completions",
        json={"choices": [{"message": {"content": "Coder done", "tool_calls": []}}]},
    )

    from aibes_agent.tools.agent import AgentProfile

    plan = Plan(
        task="T",
        steps=[
            PlanStep(step_id="1", description="Write code", agent_profile="coder"),
        ],
    )
    profiles = {
        "coder": AgentProfile(name="coder", system_prompt="You are a coder.", tools=["FileRead"])
    }
    executor = PlanExecutor(llm=client, registry=registry, profiles=profiles)
    result = await executor.execute(plan)
    assert result.steps[0].status == "done"
    assert result.steps[0].result == "Coder done"
