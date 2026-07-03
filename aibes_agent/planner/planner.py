"""Planner: generate, validate, and replan structured execution plans."""

from __future__ import annotations

import json
from typing import Dict, List, Optional

from loguru import logger

from aibes_agent.core.llm import LLMClient
from aibes_agent.core.tool_registry import ToolRegistry
from aibes_agent.planner.models import Plan, PlanStep
from aibes_agent.tools.agent import AgentProfile


class Planner:
    """Generate structured execution plans for complex tasks."""

    def __init__(
        self,
        llm: LLMClient,
        registry: ToolRegistry,
        profiles: Optional[Dict[str, AgentProfile]] = None,
        max_steps: int = 10,
    ) -> None:
        self.llm = llm
        self.registry = registry
        self.profiles = profiles or {}
        self.max_steps = max_steps

    def _available_tools(self) -> List[str]:
        return self.registry.list_tools()

    def _available_profiles(self) -> List[str]:
        return list(self.profiles.keys())

    @staticmethod
    def _extract_json(text: str) -> str:
        """Strip markdown fences and return the first JSON object."""
        text = text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        return text

    async def plan(self, task: str) -> Plan:
        """Generate a validated plan for *task*."""
        prompt = self._build_plan_prompt(task)
        response = await self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            temperature=0.2,
        )
        raw = self._extract_json(response.content)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.warning("Planner failed to parse LLM response as JSON: {}", exc)
            return self._fallback_plan(task, f"JSON parse error: {exc}")

        try:
            candidate = Plan.from_dict(data)
            candidate.task = task
        except Exception as exc:
            logger.warning("Planner failed to build Plan from LLM output: {}", exc)
            return self._fallback_plan(task, f"Plan build error: {exc}")

        if not self.validate(candidate):
            logger.warning("Planner produced invalid plan; using fallback plan")
            return self._fallback_plan(task, "Validation failed")

        # Trim to max_steps.
        if len(candidate.steps) > self.max_steps:
            candidate.steps = candidate.steps[: self.max_steps]
        return candidate

    def validate(self, plan: Plan) -> bool:
        """Validate that referenced tools and profiles exist."""
        available_tools = set(self._available_tools())
        available_profiles = set(self._available_profiles())
        step_ids = {step.step_id for step in plan.steps}

        for step in plan.steps:
            if step.tool is not None and step.tool not in available_tools:
                logger.warning(
                    "Plan step '{}' references unknown tool '{}'", step.step_id, step.tool
                )
                return False
            if step.agent_profile is not None and step.agent_profile not in available_profiles:
                logger.warning(
                    "Plan step '{}' references unknown profile '{}'",
                    step.step_id,
                    step.agent_profile,
                )
                return False
            for dep in step.depends_on:
                if dep not in step_ids:
                    logger.warning("Plan step '{}' depends on missing step '{}'", step.step_id, dep)
                    return False
        return True

    async def decompose(self, task: str) -> List[str]:
        """Decompose a task into a list of subtasks."""
        prompt = (
            f"Decompose the following task into 3-7 concise subtasks. "
            f"Return only a JSON array of strings.\n\nTask: {task}\n\nSubtasks:"
        )
        response = await self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
            temperature=0.2,
        )
        raw = self._extract_json(response.content)
        try:
            items = json.loads(raw)
            if isinstance(items, list):
                return [str(item) for item in items]
        except json.JSONDecodeError:
            pass
        return [task]

    async def replan(self, task: str, failed_plan: Plan, reason: str) -> Plan:
        """Generate a new plan based on the failure reason."""
        prompt = (
            f"The following plan failed for task: {task}\n"
            f"Failure reason: {reason}\n\n"
            f"Original plan:\n{json.dumps(failed_plan.to_dict(), ensure_ascii=False, indent=2)}\n\n"
            f"Available tools: {self._available_tools()}\n"
            f"Available agent profiles: {self._available_profiles()}\n\n"
            f"Create a revised plan as JSON with the same schema. "
            f"Return only the JSON object."
        )
        response = await self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            temperature=0.2,
        )
        raw = self._extract_json(response.content)
        try:
            data = json.loads(raw)
            candidate = Plan.from_dict(data)
            candidate.task = task
        except Exception as exc:
            logger.warning("Planner failed to replan: {}", exc)
            return self._fallback_plan(task, f"Replan error: {exc}")

        if not self.validate(candidate):
            return self._fallback_plan(task, "Replan validation failed")
        return candidate

    def _build_plan_prompt(self, task: str) -> str:
        return (
            "You are a planning assistant. Create a step-by-step plan for the task below.\n\n"
            f"Task: {task}\n\n"
            f"Available tools: {self._available_tools()}\n"
            f"Available agent profiles: {self._available_profiles()}\n\n"
            "Return a JSON object with a 'steps' array. Each step must have:\n"
            "- step_id: unique string\n"
            "- description: what to do\n"
            "- tool (optional): exact name of a tool to call\n"
            "- agent_profile (optional): exact name of an agent profile to delegate to\n"
            "- depends_on (optional): list of step_ids that must finish first\n\n"
            "If a step needs a sub-agent, use agent_profile. If it needs a single tool, use tool.\n"
            "Do not use both tool and agent_profile in the same step.\n\n"
            "Return only the JSON object."
        )

    def _fallback_plan(self, task: str, reason: str) -> Plan:
        """Return a single-step plan that delegates to the default profile if available."""
        profile = "default" if "default" in self.profiles else None
        return Plan(
            task=task,
            steps=[
                PlanStep(
                    step_id="1",
                    description=f"Execute task directly. (Planner fallback: {reason})",
                    agent_profile=profile,
                )
            ],
        )
