import os
import shutil

import pytest

from aibes_agent.tools.base import ToolContext
from aibes_agent.tools.search import GlobTool, GrepTool


@pytest.mark.skipif(shutil.which("rg") is None, reason="ripgrep not installed")
@pytest.mark.asyncio
async def test_grep_content(tmp_path):
    file = tmp_path / "sample.py"
    file.write_text("def hello():\n    return 'world'\n", encoding="utf-8")

    grep = GrepTool()
    ctx = ToolContext(cwd=str(tmp_path))
    result = await grep.call(
        grep.input_model(pattern="hello", path=str(tmp_path), output_mode="content"),
        ctx,
    )
    assert result.success
    assert "hello" in result.content


@pytest.mark.skipif(shutil.which("rg") is None, reason="ripgrep not installed")
@pytest.mark.asyncio
async def test_grep_files_with_matches(tmp_path):
    file = tmp_path / "sample.py"
    file.write_text("x = 1\n", encoding="utf-8")

    grep = GrepTool()
    ctx = ToolContext(cwd=str(tmp_path))
    result = await grep.call(
        grep.input_model(pattern="x = 1", path=str(tmp_path)),
        ctx,
    )
    assert result.success
    assert "sample.py" in result.content


@pytest.mark.skipif(shutil.which("rg") is None, reason="ripgrep not installed")
@pytest.mark.asyncio
async def test_grep_no_matches(tmp_path):
    file = tmp_path / "sample.py"
    file.write_text("x = 1\n", encoding="utf-8")

    grep = GrepTool()
    ctx = ToolContext(cwd=str(tmp_path))
    result = await grep.call(
        grep.input_model(pattern="nonexistent_pattern_12345", path=str(tmp_path)),
        ctx,
    )
    assert result.success
    assert "No matches" in result.content


@pytest.mark.asyncio
async def test_grep_rg_not_found(monkeypatch, tmp_path):
    monkeypatch.setattr(shutil, "which", lambda _: None)
    grep = GrepTool()
    ctx = ToolContext(cwd=str(tmp_path))
    result = await grep.call(grep.input_model(pattern="x"), ctx)
    assert not result.success
    assert "ripgrep" in result.error


@pytest.mark.asyncio
async def test_glob(tmp_path):
    (tmp_path / "a.py").write_text("", encoding="utf-8")
    (tmp_path / "b.py").write_text("", encoding="utf-8")

    glob = GlobTool()
    ctx = ToolContext(cwd=str(tmp_path))
    result = await glob.call(glob.input_model(pattern="*.py"), ctx)
    assert result.success
    assert "a.py" in result.content
    assert "b.py" in result.content


@pytest.mark.asyncio
async def test_glob_directory(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "file.txt").write_text("", encoding="utf-8")

    glob = GlobTool()
    ctx = ToolContext(cwd=str(tmp_path))
    result = await glob.call(glob.input_model(pattern="sub/*.txt"), ctx)
    assert result.success
    assert "file.txt" in result.content
