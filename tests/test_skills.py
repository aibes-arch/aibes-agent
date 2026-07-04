import pytest

from aibes_agent.core.engine import AgentConfig
from aibes_agent.core.tool_registry import ToolRegistry
from aibes_agent.skills import Skill, SkillBuilder, SkillLoader
from aibes_agent.tools import FileReadTool, GrepTool
from aibes_agent.tools.agent import AgentProfile


def test_load_skill(tmp_path):
    skill_dir = tmp_path / "code-review"
    skill_dir.mkdir()
    (skill_dir / "skill.yaml").write_text(
        """
name: code-review
description: Review code for correctness and style.
system_prompt: |
  You are a strict code reviewer.
tools:
  - FileRead
  - Grep
mcp_servers:
  - filesystem
profiles:
  security:
    system_prompt: Focus on security.
    tools:
      - FileRead
    max_turns: 5
""",
        encoding="utf-8",
    )

    loader = SkillLoader(search_paths=[str(tmp_path)])
    skills = loader.load_all()
    assert len(skills) == 1
    skill = skills[0]
    assert isinstance(skill, Skill)
    assert skill.name == "code-review"
    assert "strict code reviewer" in skill.system_prompt
    assert skill.tools == ["FileRead", "Grep"]
    assert skill.mcp_servers == ["filesystem"]
    assert "security" in skill.profiles
    assert skill.profiles["security"].max_turns == 5


def test_load_all_overrides_by_name(tmp_path):
    first = tmp_path / "skills1"
    first.mkdir()
    demo1 = first / "demo"
    demo1.mkdir()
    (demo1 / "skill.yaml").write_text("name: demo\nsystem_prompt: first\n", encoding="utf-8")
    second = tmp_path / "skills2"
    second.mkdir()
    demo2 = second / "demo"
    demo2.mkdir()
    (demo2 / "skill.yaml").write_text("name: demo\nsystem_prompt: second\n", encoding="utf-8")

    loader = SkillLoader(search_paths=[str(first), str(second)])
    skills = loader.load_all()
    assert len(skills) == 1
    assert skills[0].system_prompt.strip() == "second"


def test_build_config_merges_prompts():
    skill = Skill(
        name="s",
        system_prompt="Skill instructions.",
        tools=["FileRead"],
    )
    base = AgentConfig(system_prompt="Base instructions.")
    builder = SkillBuilder([skill], tool_pool={"FileRead": FileReadTool()})
    config = builder.build_config(base)
    assert "Base instructions." in config.system_prompt
    assert "Skill instructions." in config.system_prompt


def test_build_registry():
    skill = Skill(
        name="s",
        tools=["FileRead", "Grep"],
    )
    builder = SkillBuilder(
        [skill],
        tool_pool={
            "FileRead": FileReadTool(),
            "Grep": GrepTool(),
        },
    )
    registry = builder.build_registry()
    assert isinstance(registry, ToolRegistry)
    assert registry.has("FileRead")
    assert registry.has("Grep")


def test_build_registry_unknown_tool_raises():
    skill = Skill(name="s", tools=["MissingTool"])
    builder = SkillBuilder([skill], tool_pool={})
    with pytest.raises(ValueError, match="unknown tool 'MissingTool'"):
        builder.build_registry()


def test_build_profiles():
    from aibes_agent.skills.skill import SkillProfile

    skill = Skill(
        name="review",
        system_prompt="You review.",
        tools=["FileRead"],
        profiles={
            "security": SkillProfile(
                name="security",
                system_prompt="security focus",
                tools=["Grep"],
                max_turns=3,
            )
        },
    )
    builder = SkillBuilder([skill], tool_pool={"FileRead": FileReadTool()})
    profiles = builder.build_profiles()
    assert "review" in profiles
    assert "security" in profiles
    assert isinstance(profiles["security"], AgentProfile)
    assert profiles["security"].max_turns == 3


def test_load_skill_markdown(tmp_path):
    skill_dir = tmp_path / "markdown-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: markdown-skill
description: A skill defined in SKILL.md.
---

# Markdown body

This is the system prompt.
""",
        encoding="utf-8",
    )

    loader = SkillLoader(search_paths=[str(tmp_path)])
    skills = loader.load_all()
    assert len(skills) == 1
    skill = skills[0]
    assert skill.name == "markdown-skill"
    assert skill.description == "A skill defined in SKILL.md."
    assert "Markdown body" in skill.system_prompt
    assert skill.restrict_tools is False


def test_unrestricted_skill_keeps_all_tools():
    """Skills without explicit tools should not empty the tool registry."""
    skill = Skill(name="unrestricted", system_prompt="Use any tool.", restrict_tools=False)
    builder = SkillBuilder(
        [skill],
        tool_pool={"FileRead": FileReadTool(), "Grep": GrepTool()},
    )
    registry = builder.build_registry()
    assert registry.has("FileRead")
    assert registry.has("Grep")


def test_restricted_skill_with_empty_tools_has_no_tools():
    """Explicitly restricted skills with empty tools keep the registry empty."""
    skill = Skill(name="restricted", tools=[], restrict_tools=True)
    builder = SkillBuilder(
        [skill],
        tool_pool={"FileRead": FileReadTool(), "Grep": GrepTool()},
    )
    registry = builder.build_registry()
    assert not registry.has("FileRead")
    assert not registry.has("Grep")
