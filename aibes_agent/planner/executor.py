"""PlanExecutor: execute a structured plan step by step."""

from __future__ import annotations

from typing import Dict, List, Optional

from loguru import logger

from aibes_agent.core.engine import AgentConfig, AgentLoop
from aibes_agent.core.llm import LLMClient
from aibes_agent.core.tool_registry import ToolRegistry
from aibes_agent.permissions.engine import PermissionEngine
from aibes_agent.planner.models import Plan, PlanStep
from aibes_agent.tools.agent import AgentProfile
from aibes_agent.tools.base import ToolContext


class PlanExecutor:
    """Execute a Plan by running each step through a sub-agent."""

    def __init__(
        self,
        llm: LLMClient,
        registry: ToolRegistry,
        profiles: Optional[Dict[str, AgentProfile]] = None,
        permission_engine: Optional[PermissionEngine] = None,
        tool_context: Optional[ToolContext] = None,
        max_turns_per_step: int = 10,
    ) -> None:
        self.llm = llm
        self.registry = registry
        self.profiles = profiles or {}
        self.permission_engine = permission_engine
        self.tool_context = tool_context or ToolContext(cwd="/")
        self.max_turns_per_step = max_turns_per_step

    async def execute(self, plan: Plan) -> Plan:
        """Execute *plan* and return the updated plan with results."""
        order = self._topological_order(plan)
        for step_id in order:
            step = self._step_by_id(plan, step_id)
            if step is None:
                continue

            # Skip if any dependency failed.
            dep_failed = False
            for dep_id in step.depends_on:
                dep_step = self._step_by_id(plan, dep_id)
                if dep_step is not None and dep_step.status == "failed":
                    dep_failed = True
                    break
            if dep_failed:
                step.status = "failed"
                step.result = "Skipped because a dependency failed."
                continue

            step.status = "running"
            try:
                result = await self._run_step(step)
                step.status = "done"
                step.result = result
            except Exception as exc:
                logger.warning("Plan step '{}' failed: {}", step_id, exc)
                step.status = "failed"
                step.result = f"Error: {exc}"

        return plan

    async def _run_step(self, step: PlanStep) -> str:
        """Run a single step using a constrained AgentLoop."""
        tool_names, system_prompt = self._step_context(step)
        step_registry = self.registry.subset(tool_names)

        config = AgentConfig(
            system_prompt=system_prompt,
            max_turns=self.max_turns_per_step,
        )
        agent = AgentLoop(
            llm=self.llm,
            registry=step_registry,
            config=config,
            permission_engine=self.permission_engine,
            tool_context=self.tool_context,
        )

        final_content = ""
        async for event in agent.run(step.description):
            if event["type"] == "final":
                final_content = event.get("content", "")
            elif event["type"] == "error":
                raise RuntimeError(event.get("message", "Step execution failed"))
        return final_content

    def _step_context(self, step: PlanStep) -> tuple[List[str], str]:
        """Return tool names and system prompt for a step."""
        if step.agent_profile and step.agent_profile in self.profiles:
            profile = self.profiles[step.agent_profile]
            tool_names = profile.tools or self.registry.list_tools()
            system_prompt = (
                f"You are the '{profile.name}' agent profile.\n"
                f"{profile.system_prompt}\n\n"
                f"Execute this plan step: {step.description}"
            )
            return tool_names, system_prompt

        if step.tool:
            tool_names = [step.tool]
            system_prompt = (
                f"You have access to the tool '{step.tool}'. "
                f"Use it to complete this step: {step.description}"
            )
            return tool_names, system_prompt

        tool_names = self.registry.list_tools()
        system_prompt = (
            f"Execute the following plan step using the available tools.\n"
            f"Available tools: {tool_names}\n\n"
            f"Step: {step.description}"
        )
        return tool_names, system_prompt

    @staticmethod
    def _topological_order(plan: Plan) -> List[str]:
        """Return step_ids in dependency-respecting order."""
        graph = {step.step_id: set(step.depends_on) for step in plan.steps}
        order: List[str] = []
        ready = {sid for sid, deps in graph.items() if not deps}
        while ready:
            sid = sorted(ready)[0]
            ready.remove(sid)
            order.append(sid)
            for other, deps in graph.items():
                if sid in deps:
                    deps.remove(sid)
                    if not deps:
                        ready.add(other)
        # Append any remaining steps (cyclic deps) in definition order.
        for step in plan.steps:
            if step.step_id not in order:
                order.append(step.step_id)
        return order

    @staticmethod
    def _step_by_id(plan: Plan, step_id: str) -> Optional[PlanStep]:
        for step in plan.steps:
            if step.step_id == step_id:
                return step
        return None
