import asyncio
import importlib.util
import os
import shutil
from pathlib import Path

import pytest

from aibes_agent.tools.base import ToolContext
from aibes_agent.tools.code_review import CoverageTool, GitDiffTool, LintTool


@pytest.fixture
def ctx(tmp_path):
    return ToolContext(cwd=str(tmp_path))


@pytest.mark.asyncio
async def test_git_diff_working_tree(tmp_path):
    git = GitDiffTool()
    ctx = ToolContext(cwd=str(tmp_path))

    # If tmp_path is not a git repo, git diff should still succeed with no output
    result = await git.call(git.input_model(), ctx)
    assert result.success or "not a git repository" in result.error.lower()


@pytest.mark.asyncio
async def test_git_diff_in_repo(tmp_path):
    git = GitDiffTool()
    ctx = ToolContext(cwd=os.getcwd())
    result = await git.call(git.input_model(), ctx)
    assert result.success
    # Current repo may or may not have changes; either empty or non-empty is fine


@pytest.mark.skipif(
    __import__("shutil").which("ruff") is None,
    reason="ruff not installed",
)
@pytest.mark.asyncio
async def test_lint_ruff(tmp_path):
    lint = LintTool()
    ctx = ToolContext(cwd=str(tmp_path))

    py_file = tmp_path / "sample.py"
    py_file.write_text("x = 1\n", encoding="utf-8")

    result = await lint.call(lint.input_model(target=str(py_file), linter="ruff"), ctx)
    assert result.success


@pytest.mark.skipif(
    __import__("shutil").which("ruff") is None,
    reason="ruff not installed",
)
@pytest.mark.asyncio
async def test_lint_ruff_format_check(tmp_path):
    lint = LintTool()
    ctx = ToolContext(cwd=str(tmp_path))

    py_file = tmp_path / "sample.py"
    py_file.write_text("x=1\n", encoding="utf-8")

    result = await lint.call(
        lint.input_model(target=str(py_file), linter="ruff-format"),
        ctx,
    )
    # ruff format --check should fail because x=1 is not formatted
    assert not result.success or "reformatted" in result.content or "1 file" in result.content


@pytest.mark.skipif(
    importlib.util.find_spec("coverage") is None,
    reason="coverage not installed",
)
@pytest.mark.asyncio
async def test_coverage_report_no_data(tmp_path):
    cov = CoverageTool()
    ctx = ToolContext(cwd=str(tmp_path))
    result = await cov.call(cov.input_model(command="report"), ctx)
    assert not result.success or "No coverage data" in result.content


@pytest.mark.skipif(
    shutil.which("mypy") is None,
    reason="mypy not installed",
)
@pytest.mark.asyncio
async def test_lint_mypy(tmp_path):
    lint = LintTool()
    ctx = ToolContext(cwd=str(tmp_path))

    py_file = tmp_path / "sample.py"
    py_file.write_text("x: int = 1\n", encoding="utf-8")

    result = await lint.call(lint.input_model(target=str(py_file), linter="mypy"), ctx)
    assert result.success


@pytest.mark.skipif(
    importlib.util.find_spec("coverage") is None,
    reason="coverage not installed",
)
@pytest.mark.asyncio
async def test_coverage_parse(tmp_path):
    cov = CoverageTool()
    ctx = ToolContext(cwd=str(tmp_path))

    py_file = tmp_path / "sample.py"
    py_file.write_text("x = 1\n", encoding="utf-8")

    # Generate a .coverage database using the coverage API
    import coverage

    cov_api = coverage.Coverage(data_file=str(tmp_path / ".coverage"), source=[str(tmp_path)])
    cov_api.start()
    import importlib.util

    spec = importlib.util.spec_from_file_location("sample", str(py_file))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cov_api.stop()
    cov_api.save()

    result = await cov.call(cov.input_model(command="parse"), ctx)
    assert result.success
    assert "coverage_database" in result.content
    assert "sample.py" in result.content
