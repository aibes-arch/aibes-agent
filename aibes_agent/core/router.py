"""Simple regex-based model router."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from aibes_agent.config import RouterConfig


@dataclass
class ModelRouter:
    """Select a model name based on regex rules applied to a prompt/task."""

    default: Optional[str] = None
    rules: List[Tuple[re.Pattern, str]] = field(default_factory=list)

    @classmethod
    def from_config(cls, config: RouterConfig) -> "ModelRouter":
        rules = []
        for rule in config.rules:
            try:
                pattern = re.compile(rule.pattern)
            except re.error as exc:
                raise ValueError(f"Invalid router regex '{rule.pattern}': {exc}") from exc
            rules.append((pattern, rule.model))
        return cls(default=config.default, rules=rules)

    def route(self, text: str) -> Optional[str]:
        """Return the first matching model, or the default if none match."""
        for pattern, model in self.rules:
            if pattern.search(text):
                return model
        return self.default
