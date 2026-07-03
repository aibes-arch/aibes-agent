"""Data models for the Planner subsystem."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class PlanStep:
    """A single step in an execution plan."""

    step_id: str
    description: str
    tool: Optional[str] = None
    agent_profile: Optional[str] = None
    depends_on: List[str] = field(default_factory=list)
    status: str = "pending"  # pending | running | done | failed
    result: str = ""

    def to_dict(self) -> Dict:
        return {
            "step_id": self.step_id,
            "description": self.description,
            "tool": self.tool,
            "agent_profile": self.agent_profile,
            "depends_on": list(self.depends_on),
            "status": self.status,
            "result": self.result,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "PlanStep":
        return cls(
            step_id=str(data["step_id"]),
            description=str(data["description"]),
            tool=data.get("tool") or None,
            agent_profile=data.get("agent_profile") or None,
            depends_on=list(data.get("depends_on", [])),
        )


@dataclass
class Plan:
    """A structured execution plan for a task."""

    task: str
    steps: List[PlanStep]

    def to_dict(self) -> Dict:
        return {"task": self.task, "steps": [step.to_dict() for step in self.steps]}

    @classmethod
    def from_dict(cls, data: Dict) -> "Plan":
        return cls(
            task=str(data.get("task", "")),
            steps=[PlanStep.from_dict(s) for s in data.get("steps", [])],
        )

    def is_complete(self) -> bool:
        """Return True when all steps are done or failed."""
        return all(step.status in ("done", "failed") for step in self.steps)

    def failed_steps(self) -> List[PlanStep]:
        return [step for step in self.steps if step.status == "failed"]
