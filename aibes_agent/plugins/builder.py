"""Assemble runtime objects from loaded plugins."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from loguru import logger

from aibes_agent.core.engine import AgentConfig
from aibes_agent.core.tool_registry import ToolRegistry
from aibes_agent.plugins.plugin import Plugin
from aibes_agent.skills.skill import Skill
from aibes_agent.tools.agent import AgentProfile
from aibes_agent.tools.base import Tool


@dataclass
class PluginBuilder:
    """Collect tools, skills, and profiles contributed by plugins."""

    plugins: List[Plugin]

    def build_tools(self) -> Dict[str, Tool]:
        """Return a name->Tool mapping from all declarative plugins."""
        tools: Dict[str, Tool] = {}
        for plugin in self.plugins:
            for tool in plugin.tools:
                if tool.name in tools:
                    logger.warning(
                        "Plugin tool '{}' from {} overrides earlier plugin '{}'",
                        tool.name,
                        plugin.source,
                        tools[tool.name],
                    )
                tools[tool.name] = tool
        return tools

    def build_skills(self) -> List[Skill]:
        """Return all Skill instances exported by plugins."""
        skills: List[Skill] = []
        for plugin in self.plugins:
            skills.extend(plugin.skills)
        return skills

    def build_profiles(self) -> Dict[str, AgentProfile]:
        """Return all sub-agent profiles exported by plugins."""
        profiles: Dict[str, AgentProfile] = {}
        for plugin in self.plugins:
            for name, profile in plugin.profiles.items():
                if name in profiles:
                    raise ValueError(
                        f"Duplicate agent profile name '{name}' from plugins "
                        f"'{profiles[name]}' and '{plugin.name}'"
                    )
                profiles[name] = profile
        return profiles

    def apply_setups(self, registry: ToolRegistry, config: AgentConfig) -> None:
        """Call imperative ``setup(registry, config)`` callbacks from plugins."""
        for plugin in self.plugins:
            if plugin.setup is not None:
                try:
                    plugin.setup(registry, config)
                except Exception as exc:
                    logger.warning(
                        "Plugin '{}' setup() failed: {}",
                        plugin.name,
                        exc,
                    )
