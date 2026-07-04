"""Skill data model."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class SkillProfile:
    """A sub-agent profile defined inside a skill."""

    name: str
    system_prompt: str = ""
    tools: List[str] = field(default_factory=list)
    max_turns: int = 10
    model: Optional[str] = None


@dataclass
class Skill:
    """A reusable bundle of prompt, tools, mcp servers, and sub-agent profiles."""

    name: str
    path: Optional[Path] = None
    description: str = ""
    system_prompt: str = ""
    tools: List[str] = field(default_factory=list)
    mcp_servers: List[str] = field(default_factory=list)
    profiles: Dict[str, SkillProfile] = field(default_factory=dict)
    # When True, only ``tools`` are available; when False, the skill does not
    # restrict the tool pool and all built-in/MCP tools remain available.
    # Defaults to True to keep the historical ``skill.yaml`` semantics.
    restrict_tools: bool = True
