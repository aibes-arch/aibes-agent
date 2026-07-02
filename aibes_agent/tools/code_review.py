"""Code review domain tools for aibes-agent v0.4.0."""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field

from aibes_agent.tools.base import Tool, ToolContext, ToolResult


class GitDiffInput(BaseModel):
    commit_range: str = Field(
        "",
        description="Git commit range (e.g. 'HEAD~1' or 'main...feature'). Empty means working tree diff.",
    )
    path: str = Field("", description="Optional file or directory to limit the diff to")
    staged: bool = Field(False, description="If True, show staged diff instead of working tree")


class GitDiffTool(Tool[GitDiffInput]):
    name = "GitDiff"
    description = (
        "Get git diff for the working directory, staged changes, or a specific commit range. "
        "Use this to inspect code changes before review."
    )
    input_model = GitDiffInput

    def is_read_only(self, input: GitDiffInput) -> bool:
        return True

    async def call(self, input: GitDiffInput, context: ToolContext) -> ToolResult:
        git = shutil.which("git")
        if not git:
            return ToolResult.fail("git not found in PATH")

        cmd = [git, "diff"]
        if input.staged:
            cmd.append("--cached")
        elif input.commit_range:
            cmd.append(input.commit_range)

        if input.path:
            cmd.append("--")
            cmd.append(input.path)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=context.cwd,
            )
            stdout, stderr = await proc.communicate()
            out = stdout.decode("utf-8", errors="replace")
            err = stderr.decode("utf-8", errors="replace")

            if proc.returncode != 0:
                return ToolResult.fail(f"git diff failed: {err}", content=out)

            return ToolResult.ok(out or "No diff output (no changes).")
        except Exception as e:
            return ToolResult.fail(f"GitDiff failed: {e}")


class LintInput(BaseModel):
    target: str = Field(".", description="File or directory to lint")
    linter: str = Field(
        "ruff",
        description="Linter to run: 'ruff', 'ruff-format', or 'mypy'",
    )
    extra_args: List[str] = Field(
        default_factory=list,
        description="Additional CLI arguments passed to the linter",
    )


class LintTool(Tool[LintInput]):
    name = "Lint"
    description = (
        "Run a static analysis linter (ruff check, ruff format --check, or mypy) "
        "on the target path and return the output."
    )
    input_model = LintInput

    def is_read_only(self, input: LintInput) -> bool:
        # ruff format --check is read-only; ruff check and mypy are read-only
        return True

    async def call(self, input: LintInput, context: ToolContext) -> ToolResult:
        linter = input.linter.lower()

        if linter == "ruff":
            executable = shutil.which("ruff")
            cmd = [executable or "ruff", "check", input.target, *input.extra_args]
        elif linter in ("ruff-format", "ruff_format"):
            executable = shutil.which("ruff")
            cmd = [executable or "ruff", "format", "--check", input.target, *input.extra_args]
        elif linter == "mypy":
            executable = shutil.which("mypy")
            cmd = [executable or "mypy", input.target, *input.extra_args]
        else:
            return ToolResult.fail(f"Unsupported linter: {input.linter}")

        if executable is None and cmd[0] not in ("ruff", "mypy"):
            return ToolResult.fail(
                f"{input.linter} not found. Install the code_review extras: "
                "pip install aibes-agent[code_review]"
            )

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=context.cwd,
            )
            stdout, stderr = await proc.communicate()
            out = stdout.decode("utf-8", errors="replace")
            err = stderr.decode("utf-8", errors="replace")

            content = out
            if err:
                content += f"\nSTDERR:\n{err}"

            if proc.returncode == 0:
                return ToolResult.ok(content or "No lint issues found.")
            return ToolResult.fail(
                f"Lint found issues (exit code {proc.returncode})",
                content=content.strip(),
            )
        except Exception as e:
            return ToolResult.fail(f"Lint failed: {e}")


class CoverageInput(BaseModel):
    target: str = Field(".", description="Path to the project or test directory")
    command: str = Field(
        "report",
        description="Coverage command: 'report' (existing .coverage), 'run' (run tests first), or 'html'",
    )
    source: Optional[str] = Field(
        None,
        description="Source package to measure coverage for (passed to coverage run)",
    )


class CoverageTool(Tool[CoverageInput]):
    name = "Coverage"
    description = (
        "Run or parse Python test coverage. Can execute 'coverage run' to collect data "
        "or 'coverage report' to summarize existing .coverage data."
    )
    input_model = CoverageInput

    def is_read_only(self, input: CoverageInput) -> bool:
        # coverage run writes files; coverage report is read-only
        return input.command.lower() == "report"

    async def call(self, input: CoverageInput, context: ToolContext) -> ToolResult:
        try:
            import coverage  # type: ignore[import-not-found]
        except ImportError:
            return ToolResult.fail(
                "coverage package not found. Install the code_review extras: "
                "pip install aibes-agent[code_review]"
            )

        cmd = input.command.lower()
        try:
            if cmd == "run":
                coverage_exe = shutil.which("coverage")
                if not coverage_exe:
                    return ToolResult.fail("coverage CLI not found in PATH")

                run_cmd = [coverage_exe, "run", "-m", "pytest", input.target]
                if input.source:
                    run_cmd = [
                        coverage_exe,
                        "run",
                        "--source",
                        input.source,
                        "-m",
                        "pytest",
                        input.target,
                    ]

                proc = await asyncio.create_subprocess_exec(
                    *run_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=context.cwd,
                )
                stdout, stderr = await proc.communicate()
                out = stdout.decode("utf-8", errors="replace")
                err = stderr.decode("utf-8", errors="replace")

                if proc.returncode not in (
                    0,
                    1,
                ):  # pytest exit 1 means test failures, but coverage is fine
                    return ToolResult.fail(f"coverage run failed: {err}", content=out)

                # Then produce a report
                report_proc = await asyncio.create_subprocess_exec(
                    coverage_exe,
                    "report",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=context.cwd,
                )
                report_stdout, report_stderr = await report_proc.communicate()
                report_out = report_stdout.decode("utf-8", errors="replace")
                report_err = report_stderr.decode("utf-8", errors="replace")

                content = f"{out}\n\nCoverage Report:\n{report_out}"
                if report_err:
                    content += f"\nSTDERR:\n{report_err}"
                return ToolResult.ok(content.strip())

            elif cmd == "report":
                coverage_exe = shutil.which("coverage")
                if not coverage_exe:
                    return ToolResult.fail("coverage CLI not found in PATH")

                proc = await asyncio.create_subprocess_exec(
                    coverage_exe,
                    "report",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=context.cwd,
                )
                stdout, stderr = await proc.communicate()
                out = stdout.decode("utf-8", errors="replace")
                err = stderr.decode("utf-8", errors="replace")

                if proc.returncode != 0:
                    return ToolResult.fail(f"coverage report failed: {err}", content=out)
                return ToolResult.ok(out or "No coverage data found.")

            elif cmd == "html":
                coverage_exe = shutil.which("coverage")
                if not coverage_exe:
                    return ToolResult.fail("coverage CLI not found in PATH")

                proc = await asyncio.create_subprocess_exec(
                    coverage_exe,
                    "html",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=context.cwd,
                )
                stdout, stderr = await proc.communicate()
                out = stdout.decode("utf-8", errors="replace")
                err = stderr.decode("utf-8", errors="replace")

                if proc.returncode != 0:
                    return ToolResult.fail(f"coverage html failed: {err}", content=out)
                return ToolResult.ok(out or "HTML coverage report generated.")

            else:
                return ToolResult.fail(f"Unsupported coverage command: {input.command}")
        except Exception as e:
            return ToolResult.fail(f"Coverage failed: {e}")
