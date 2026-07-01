"""Build AgentConfig / ToolRegistry / Agent profiles from loaded Skills."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from aibes_agent.core.engine import AgentConfig
from aibes_agent.core.tool_registry import ToolRegistry
from aibes_agent.skills.skill import Skill, SkillProfile
from aibes_agent.tools.agent import AgentProfile
from aibes_agent.tools.base import Tool


class SkillBuilder:
    """Assemble runtime objects from a list of Skills."""

    def __init__(
        self,
        skills: List[Skill],
        tool_pool: Dict[str, Tool],
        mcp_tools: Optional[Dict[str, Tool]] = None,
    ) -> None:
        self.skills = skills
        self.tool_pool = tool_pool
        self.mcp_tools = mcp_tools or {}

    def build_config(self, base: Optional[AgentConfig] = None) -> AgentConfig:
        """Merge base config system prompt with all skill system prompts."""
        base = base or AgentConfig()
        prompt_parts: List[str] = []
        if base.system_prompt:
            prompt_parts.append(base.system_prompt)
        for skill in self.skills:
            if skill.system_prompt:
                prompt_parts.append(skill.system_prompt)
        merged_prompt = "\n\n".join(prompt_parts)
        return AgentConfig(
            system_prompt=merged_prompt,
            max_turns=base.max_turns,
            max_tokens_per_turn=base.max_tokens_per_turn,
            temperature=base.temperature,
            auto_compact=base.auto_compact,
        )

    def build_registry(self) -> ToolRegistry:
        """Register tools referenced by skills plus all available MCP tools.

        If no skills are loaded, the entire built-in tool pool is registered so
        that a default configuration still works out of the box.
        """
        registry = ToolRegistry()
        registered: set[str] = set()

        if not self.skills:
            for tool in self.tool_pool.values():
                registry.register(tool)
            registered.update(self.tool_pool.keys())
        else:
            for skill in self.skills:
                for tool_name in skill.tools:
                    if tool_name in registered:
                        continue
                    matched = self.tool_pool.get(tool_name)
                    if matched is None:
                        matched = self.mcp_tools.get(tool_name)
                    if matched is None:
                        raise ValueError(
                            f"Skill '{skill.name}' references unknown tool '{tool_name}'"
                        )
                    registry.register(matched)
                    registered.add(tool_name)

        for name, tool in self.mcp_tools.items():
            if name not in registered:
                registry.register(tool)
                registered.add(name)

        return registry

    def build_profiles(self) -> Dict[str, AgentProfile]:
        """Convert skill profiles into AgentTool profiles.

        Also creates an implicit profile for each skill so it can be delegated to
        as a sub-agent. If no explicit ``default`` profile exists, the first skill
        is duplicated as ``default`` so ``AgentTool`` can be instantiated.
        """
        profiles: Dict[str, AgentProfile] = {}
        for skill in self.skills:
            # Explicit profiles defined in the skill
            for prof in skill.profiles.values():
                if prof.name in profiles:
                    raise ValueError(f"Duplicate agent profile name: {prof.name}")
                profiles[prof.name] = _skill_profile_to_agent_profile(prof)

            # Implicit profile for the whole skill
            if skill.name not in profiles:
                profiles[skill.name] = AgentProfile(
                    name=skill.name,
                    system_prompt=skill.system_prompt,
                    tools=skill.tools,
                    max_turns=10,
                )

        if profiles and "default" not in profiles and self.skills:
            first = self.skills[0]
            profiles["default"] = AgentProfile(
                name="default",
                system_prompt=first.system_prompt,
                tools=first.tools,
                max_turns=10,
            )

        return profiles

    def build(
        self,
        base_config: Optional[AgentConfig] = None,
    ) -> Tuple[AgentConfig, ToolRegistry, Dict[str, AgentProfile]]:
        """Build the complete runtime triple."""
        return (
            self.build_config(base_config),
            self.build_registry(),
            self.build_profiles(),
        )


def _skill_profile_to_agent_profile(prof: SkillProfile) -> AgentProfile:
    return AgentProfile(
        name=prof.name,
        system_prompt=prof.system_prompt,
        tools=prof.tools,
        max_turns=prof.max_turns,
        model=prof.model,
    )
