"""Plugin data model."""

from __future__ import annotations

import types
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Dict, List, Optional

from aibes_agent.skills.skill import Skill
from aibes_agent.tools.agent import AgentProfile
from aibes_agent.tools.base import Tool

if TYPE_CHECKING:
    from aibes_agent.core.engine import AgentConfig
    from aibes_agent.core.tool_registry import ToolRegistry


SetupCallback = Callable[["ToolRegistry", "AgentConfig"], None]


@dataclass
class Plugin:
    """A discovered plugin with its exported resources.

    The underlying Python module remains importable and usable outside the
    framework, so plugin business logic can be called independently.
    """

    name: str
    version: str
    module: types.ModuleType
    tools: List[Tool] = field(default_factory=list)
    skills: List[Skill] = field(default_factory=list)
    profiles: Dict[str, AgentProfile] = field(default_factory=dict)
    setup: Optional[SetupCallback] = None
    source: str = ""
