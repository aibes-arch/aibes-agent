"""Tests for the aibes-agent CLI."""

from __future__ import annotations

import textwrap

from typer.testing import CliRunner

from aibes_agent.cli import app

runner = CliRunner()


def test_plugins_list_empty() -> None:
    result = runner.invoke(app, ["plugins", "list"])
    assert result.exit_code == 0
    assert "No plugins discovered" in result.output


def test_plugins_list_discovers_plugin(tmp_path) -> None:
    plugins_dir = tmp_path / "plugins"
    plugin_dir = plugins_dir / "demo"
    plugin_dir.mkdir(parents=True)
    plugin_dir.joinpath("__init__.py").write_text(
        textwrap.dedent("""\
            from pydantic import BaseModel
            from aibes_agent.tools import Tool, ToolContext, ToolResult

            class DemoInput(BaseModel):
                pass

            class DemoTool(Tool[DemoInput]):
                name = "Demo"
                description = "Demo tool."
                input_model = DemoInput

                async def call(self, input, context):
                    return ToolResult.ok("demo")

            __aibes_plugin__ = {
                "name": "demo",
                "version": "1.0.0",
                "tools": [DemoTool],
            }
            """),
        encoding="utf-8",
    )

    config = tmp_path / "cfg.yaml"
    config.write_text(
        f"plugins:\n  paths:\n    - {plugins_dir}\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["plugins", "list", "--config", str(config), "--tools"],
    )
    assert result.exit_code == 0
    assert "demo" in result.output
    assert "Demo" in result.output
