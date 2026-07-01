"""minagent CLI entry point.

Usage:
    minagent [--yes-to-all] <script.py> [args...]
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer

app = typer.Typer(help="minagent — minimal Python agent framework CLI")


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
        Optional[list[str]],
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
) -> None:
    """Run an agent script."""
    if yes_to_all:
        os.environ["MINAGENT_YES_TO_ALL"] = "1"
    _run_script(Path(script), args or [])


if __name__ == "__main__":
    app()
