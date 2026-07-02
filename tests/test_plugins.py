"""Tests for the aibes-agent plugin system."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest
from pydantic import BaseModel

from aibes_agent.config import MinagentConfig, PluginsConfig
from aibes_agent.core.engine import AgentConfig
from aibes_agent.core.tool_registry import ToolRegistry
from aibes_agent.plugins import PluginBuilder, PluginLoader
from aibes_agent.skills import SkillBuilder
from aibes_agent.tools import Tool, ToolContext, ToolResult


class _EchoInput(BaseModel):
    message: str


class _EchoTool(Tool[_EchoInput]):
    name = "Echo"
    description = "Echoes the input message."
    input_model = _EchoInput

    async def call(self, input: _EchoInput, context: ToolContext) -> ToolResult:
        return ToolResult.ok(input.message)


def _make_plugin_dir(root: Path, name: str, init_content: str) -> Path:
    directory = root / name
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "__init__.py").write_text(init_content, encoding="utf-8")
    return directory


def test_load_declarative_path_plugin(tmp_path):
    directory = _make_plugin_dir(
        tmp_path,
        "greet_plugin",
        textwrap.dedent("""\
            from pydantic import BaseModel
            from aibes_agent.tools import Tool, ToolContext, ToolResult

            class GreetInput(BaseModel):
                name: str

            class GreetTool(Tool[GreetInput]):
                name = "Greet"
                description = "Greet someone."
                input_model = GreetInput

                async def call(self, input, context):
                    return ToolResult.ok(f"Hello, {input.name}!")

            def greet(name: str) -> str:
                return f"Hello, {name}!"

            __aibes_plugin__ = {
                "name": "greet",
                "version": "1.2.0",
                "tools": [GreetTool],
            }
            """),
    )

    plugins = PluginLoader(search_paths=[str(tmp_path)], load_entry_points=False).load_all()
    assert len(plugins) == 1
    plugin = plugins[0]
    assert plugin.name == "greet"
    assert plugin.version == "1.2.0"
    assert len(plugin.tools) == 1
    assert plugin.tools[0].name == "Greet"

    # The plugin business logic can be called independently.
    assert plugin.module.greet("World") == "Hello, World!"


def test_plugin_yaml_overrides_metadata(tmp_path):
    directory = _make_plugin_dir(
        tmp_path,
        "meta_plugin",
        textwrap.dedent("""\
            __aibes_plugin__ = {
                "name": "old_name",
                "version": "0.0.1",
            }
            """),
    )
    (directory / "plugin.yaml").write_text(
        textwrap.dedent("""\
            name: new_name
            version: 2.0.0
            """),
        encoding="utf-8",
    )

    plugins = PluginLoader(search_paths=[str(tmp_path)], load_entry_points=False).load_all()
    assert len(plugins) == 1
    assert plugins[0].name == "new_name"
    assert plugins[0].version == "2.0.0"


def test_setup_callback_registers_tool(tmp_path):
    directory = _make_plugin_dir(
        tmp_path,
        "setup_plugin",
        textwrap.dedent("""\
            from pydantic import BaseModel
            from aibes_agent.tools import Tool, ToolContext, ToolResult

            class SetupInput(BaseModel):
                value: int

            class SetupTool(Tool[SetupInput]):
                name = "SetupTool"
                description = "Tool registered via setup."
                input_model = SetupInput

                async def call(self, input, context):
                    return ToolResult.ok(str(input.value * 2))

            def setup(registry, config):
                registry.register(SetupTool())
            """),
    )

    plugins = PluginLoader(search_paths=[str(tmp_path)], load_entry_points=False).load_all()
    assert len(plugins) == 1
    assert plugins[0].setup is not None

    registry = ToolRegistry()
    builder = PluginBuilder(plugins)
    builder.apply_setups(registry, AgentConfig())
    assert registry.has("SetupTool")


@pytest.mark.asyncio
async def test_plugin_tool_in_skill_builder_registry(tmp_path):
    directory = _make_plugin_dir(
        tmp_path,
        "skill_plugin",
        textwrap.dedent("""\
            from pydantic import BaseModel
            from aibes_agent.tools import Tool, ToolContext, ToolResult

            class DoubleInput(BaseModel):
                n: int

            class DoubleTool(Tool[DoubleInput]):
                name = "Double"
                description = "Doubles a number."
                input_model = DoubleInput

                async def call(self, input, context):
                    return ToolResult.ok(str(input.n * 2))

            __aibes_plugin__ = {
                "name": "math",
                "tools": [DoubleTool],
            }
            """),
    )

    plugins = PluginLoader(search_paths=[str(tmp_path)], load_entry_points=False).load_all()
    plugin_builder = PluginBuilder(plugins)
    tool_pool = plugin_builder.build_tools()

    builder = SkillBuilder([], tool_pool)
    _, registry, _ = builder.build()

    assert registry.has("Double")
    result = await registry.execute(
        [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "Double", "arguments": {"n": 21}},
            }
        ],
        ToolContext(cwd=str(tmp_path)),
    )
    assert result[0]["content"] == "42"


def test_plugin_skills_and_profiles(tmp_path):
    directory = _make_plugin_dir(
        tmp_path,
        "profile_plugin",
        textwrap.dedent("""\
            from aibes_agent.skills import Skill, SkillProfile
            from aibes_agent.tools import AgentProfile

            __aibes_plugin__ = {
                "name": "profiles",
                "skills": [
                    Skill(
                        name="translator",
                        system_prompt="You are a translator.",
                        tools=["FileRead"],
                    ),
                ],
                "profiles": {
                    "coder": AgentProfile(
                        name="coder",
                        system_prompt="You are a coder.",
                        tools=["FileRead"],
                    ),
                },
            }
            """),
    )

    plugins = PluginLoader(search_paths=[str(tmp_path)], load_entry_points=False).load_all()
    builder = PluginBuilder(plugins)
    assert [s.name for s in builder.build_skills()] == ["translator"]
    assert list(builder.build_profiles().keys()) == ["coder"]


def test_duplicate_plugin_uses_first(tmp_path):
    for name in ("first", "second"):
        _make_plugin_dir(
            tmp_path,
            name,
            textwrap.dedent(f"""\
                __aibes_plugin__ = {{
                    "name": "dup",
                    "version": "{name}",
                }}
                """),
        )

    plugins = PluginLoader(search_paths=[str(tmp_path)], load_entry_points=False).load_all()
    assert len(plugins) == 1
    assert plugins[0].version == "first"


def test_skip_module_without_contract(tmp_path):
    _make_plugin_dir(
        tmp_path,
        "empty_plugin",
        textwrap.dedent("""\
            # No __aibes_plugin__ or setup
            """),
    )

    plugins = PluginLoader(search_paths=[str(tmp_path)], load_entry_points=False).load_all()
    assert plugins == []


def test_config_parses_plugins_section():
    cfg = MinagentConfig.from_dict(
        {
            "plugins": {
                "auto_load": False,
                "entry_points": False,
                "paths": ["./custom-plugins"],
            }
        }
    )
    assert cfg.plugins == PluginsConfig(
        auto_load=False,
        entry_points=False,
        paths=["./custom-plugins"],
    )


def test_default_config_has_plugins():
    cfg = MinagentConfig()
    assert cfg.plugins.auto_load is True
    assert cfg.plugins.entry_points is True
    assert cfg.plugins.paths == [".aibes-agent/plugins"]
