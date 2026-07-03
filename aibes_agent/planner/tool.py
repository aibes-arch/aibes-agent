"""PlannerTool: expose planning and execution as a Tool."""

from __future__ import annotations

from typing import Dict, Optional

from pydantic import BaseModel, Field

from aibes_agent.core.engine import AgentConfig
from aibes_agent.core.llm import LLMClient
from aibes_agent.core.tool_registry import ToolRegistry
from aibes_agent.permissions.engine import PermissionEngine
from aibes_agent.planner.executor import PlanExecutor
from aibes_agent.planner.models import Plan
from aibes_agent.planner.planner import Planner
from aibes_agent.tools.agent import AgentProfile
from aibes_agent.tools.base import Tool, ToolContext, ToolResult


class PlannerInput(BaseModel):
    task: str = Field(..., description="Complex task to plan and execute.")
    allow_replan: bool = Field(
        True,
        description="Whether to replan once if the first plan fails.",
    )


class PlannerTool(Tool[PlannerInput]):
    name = "Planner"
    description = (
        "Create and execute a multi-step plan for a complex task. "
        "Use this tool when the user request requires multiple steps or tools."
    )
    input_model = PlannerInput

    def __init__(
        self,
        llm: LLMClient,
        registry: ToolRegistry,
        profiles: Optional[Dict[str, AgentProfile]] = None,
        permission_engine: Optional[PermissionEngine] = None,
        tool_context: Optional[ToolContext] = None,
        max_steps: int = 10,
    ) -> None:
        super().__init__()
        self.planner = Planner(llm, registry, profiles, max_steps=max_steps)
        self.executor = PlanExecutor(
            llm=llm,
            registry=registry,
            profiles=profiles,
            permission_engine=permission_engine,
            tool_context=tool_context or ToolContext(cwd="/"),
        )
        self.llm = llm

    def is_read_only(self, input: PlannerInput) -> bool:
        return False

    async def call(self, input: PlannerInput, context: ToolContext) -> ToolResult:
        plan = await self.planner.plan(input.task)
        executed = await self.executor.execute(plan)

        if input.allow_replan and executed.failed_steps():
            reason = "; ".join(f"{step.step_id}: {step.result}" for step in executed.failed_steps())
            new_plan = await self.planner.replan(input.task, executed, reason)
            executed = await self.executor.execute(new_plan)

        return ToolResult.ok(self._format_result(executed))

    @staticmethod
    def _format_result(plan: Plan) -> str:
        lines = [f"Plan for: {plan.task}", ""]
        for step in plan.steps:
            icon = "✓" if step.status == "done" else "✗" if step.status == "failed" else " "
            lines.append(f"[{icon}] {step.step_id}: {step.description}")
            if step.result:
                result = step.result.replace("\n", " ")
                lines.append(f"    -> {result[:300]}{'...' if len(result) > 300 else ''}")
        return "\n".join(lines)
