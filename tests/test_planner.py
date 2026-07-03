"""Tests for the Planner module."""

from __future__ import annotations

import json

import pytest

from aibes_agent.core.llm import LLMClient
from aibes_agent.core.tool_registry import ToolRegistry
from aibes_agent.planner import Plan, Planner
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
async def test_planner_generates_valid_plan(client, registry, httpx_mock):
    httpx_mock.add_response(
        url="http://test/chat/completions",
        json={
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "steps": [
                                    {
                                        "step_id": "1",
                                        "description": "Read the file",
                                        "tool": "FileRead",
                                        "depends_on": [],
                                    },
                                    {
                                        "step_id": "2",
                                        "description": "Summarize",
                                        "depends_on": ["1"],
                                    },
                                ]
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        },
    )

    planner = Planner(llm=client, registry=registry)
    plan = await planner.plan("Read and summarize a file")

    assert plan.task == "Read and summarize a file"
    assert len(plan.steps) == 2
    assert plan.steps[0].tool == "FileRead"
    assert plan.steps[1].depends_on == ["1"]
    assert planner.validate(plan) is True


@pytest.mark.asyncio
async def test_planner_rejects_unknown_tool(client, registry, httpx_mock):
    httpx_mock.add_response(
        url="http://test/chat/completions",
        json={
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "steps": [
                                    {
                                        "step_id": "1",
                                        "description": "Do something",
                                        "tool": "UnknownTool",
                                    }
                                ]
                            }
                        )
                    }
                }
            ]
        },
    )

    planner = Planner(llm=client, registry=registry)
    plan = await planner.plan("Invalid task")
    # Validation should fail and fallback plan should be used.
    assert len(plan.steps) == 1
    assert plan.steps[0].agent_profile == "default" or plan.steps[0].agent_profile is None


@pytest.mark.asyncio
async def test_planner_decompose(client, httpx_mock):
    httpx_mock.add_response(
        url="http://test/chat/completions",
        json={"choices": [{"message": {"content": json.dumps(["A", "B", "C"])}}]},
    )

    planner = Planner(llm=client, registry=ToolRegistry())
    subtasks = await planner.decompose("Complex task")
    assert subtasks == ["A", "B", "C"]


@pytest.mark.asyncio
async def test_planner_replan(client, registry, httpx_mock):
    httpx_mock.add_response(
        url="http://test/chat/completions",
        json={
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "steps": [
                                    {
                                        "step_id": "1",
                                        "description": "Retry step",
                                        "tool": "FileRead",
                                    }
                                ]
                            }
                        )
                    }
                }
            ]
        },
    )

    planner = Planner(llm=client, registry=registry)
    failed = Plan(
        task="T",
        steps=[PlanStep(step_id="1", description="Old step", tool="FileRead", status="failed")],
    )
    new_plan = await planner.replan("T", failed, "file not found")
    assert new_plan.task == "T"
    assert new_plan.steps[0].description == "Retry step"


def test_plan_model_serialization():
    plan = Plan(
        task="T",
        steps=[PlanStep(step_id="1", description="Step 1", tool="FileRead")],
    )
    data = plan.to_dict()
    restored = Plan.from_dict(data)
    assert restored.task == plan.task
    assert restored.steps[0].tool == "FileRead"
