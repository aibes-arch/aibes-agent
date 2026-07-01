"""aibes-agent CLI entry point.

Usage:
    aibes-agent run [--yes-to-all] <script.py> [args...]
    aibes-agent web [--config path] [--host HOST] [--port PORT]
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Annotated, List, Optional

import typer

from aibes_agent.config import MinagentConfig

app = typer.Typer(help="aibes-agent — minimal Python agent framework CLI")


def _run_script(script_path: Path, script_args: list[str]) -> None:
    """Execute a Python script in a ``__main__`` namespace."""
    if not script_path.exists():
        typer.echo(f"Error: script not found: {script_path}", err=True)
        raise typer.Exit(code=2)

    if not script_path.is_file():
        typer.echo(f"Error: not a file: {script_path}", err=True)
        raise typer.Exit(code=2)

    source = script_path.read_text(encoding="utf-8")

    # Save and restore sys.argv so the script sees its own arguments.
    original_argv = sys.argv
    sys.argv = [str(script_path), *script_args]

    namespace = {
        "__name__": "__main__",
        "__file__": str(script_path.resolve()),
        "__cached__": None,
    }

    try:
        code = compile(source, str(script_path), "exec")
        exec(code, namespace)
    finally:
        sys.argv = original_argv


@app.command()
def run(
    script: Annotated[str, typer.Argument(help="Path to the agent script to run")],
    args: Annotated[
        Optional[List[str]],
        typer.Argument(help="Arguments passed to the script"),
    ] = None,
    yes_to_all: Annotated[
        bool,
        typer.Option(
            "--yes-to-all",
            "-y",
            help="Automatically answer yes to all permission prompts",
        ),
    ] = False,
    config: Annotated[
        Optional[str],
        typer.Option("--config", "-c", help="Path to aibes-agent.yaml"),
    ] = None,
    session: Annotated[
        Optional[str],
        typer.Option("--session", "-s", help="Session id for persistence"),
    ] = None,
    skill: Annotated[
        Optional[List[str]],
        typer.Option("--skill", help="Skill names to activate (can be repeated)"),
    ] = None,
) -> None:
    """Run an agent script."""
    if yes_to_all:
        os.environ["AIBES_AGENT_YES_TO_ALL"] = "1"
    if config:
        os.environ["AIBES_AGENT_CONFIG"] = config
    if session:
        os.environ["AIBES_AGENT_SESSION"] = session
    if skill:
        os.environ["AIBES_AGENT_SKILLS"] = ",".join(skill)
    _run_script(Path(script), args or [])


@app.command()
def web(
    config: Annotated[
        Optional[str],
        typer.Option("--config", "-c", help="Path to aibes-agent.yaml"),
    ] = None,
    host: Annotated[
        Optional[str],
        typer.Option("--host", help="Bind host"),
    ] = None,
    port: Annotated[
        Optional[int],
        typer.Option("--port", "-p", help="Bind port"),
    ] = None,
) -> None:
    """Start the aibes-agent Web UI server."""
    try:
        import uvicorn
    except ImportError as exc:
        typer.echo(
            "Web UI requires the 'web' extra. " "Install it with: pip install aibes-agent[web]",
            err=True,
        )
        raise typer.Exit(code=2) from exc

    cfg = MinagentConfig.load(config) if config else MinagentConfig.load()
    if host:
        cfg.web.host = host
    if port:
        cfg.web.port = port

    from aibes_agent.web.server import create_app

    web_app = create_app(cfg)
    uvicorn.run(web_app, host=cfg.web.host, port=cfg.web.port)


if __name__ == "__main__":
    app()
