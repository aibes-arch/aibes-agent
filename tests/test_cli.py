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


def test_sessions_list_empty(tmp_path) -> None:
    config = tmp_path / "cfg.yaml"
    config.write_text(
        f"session:\n  store: file\n  path: {tmp_path / 'sessions'}\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["sessions", "list", "--config", str(config)])
    assert result.exit_code == 0
    assert "No sessions found" in result.output


def test_sessions_crud(tmp_path) -> None:
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    (sessions_dir / "s1.json").write_text(
        '{"session_id": "s1", "messages": [], "tasks": [], "metadata": {}, "updated_at": 0}',
        encoding="utf-8",
    )

    config = tmp_path / "cfg.yaml"
    config.write_text(
        f"session:\n  store: file\n  path: {sessions_dir}\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["sessions", "list", "--config", str(config)])
    assert result.exit_code == 0
    assert "s1" in result.output

    result = runner.invoke(app, ["sessions", "delete", "s1", "--config", str(config)])
    assert result.exit_code == 0
    assert "Deleted session" in result.output

    result = runner.invoke(app, ["sessions", "delete", "s1", "--config", str(config)])
    assert result.exit_code == 1


def test_sessions_clear_and_cleanup(tmp_path) -> None:
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    (sessions_dir / "old.json").write_text(
        '{"session_id": "old", "messages": [], "tasks": [], "metadata": {}, "updated_at": 0}',
        encoding="utf-8",
    )

    config = tmp_path / "cfg.yaml"
    config.write_text(
        f"session:\n  store: file\n  path: {sessions_dir}\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["sessions", "cleanup", "--max-age", "1", "--config", str(config)],
    )
    assert result.exit_code == 0
    assert "Deleted 1 expired session" in result.output

    result = runner.invoke(app, ["sessions", "clear", "--config", str(config)])
    assert result.exit_code == 0
    assert "All sessions cleared" in result.output
