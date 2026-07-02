import os

import pytest

from aibes_agent.tools.base import ToolContext
from aibes_agent.tools.shell import BashTool


@pytest.mark.asyncio
async def test_bash_echo():
    bash = BashTool()
    ctx = ToolContext(cwd=os.getcwd())
    result = await bash.call(bash.input_model(command="echo hello"), ctx)
    assert result.success
    assert "hello" in result.content


@pytest.mark.asyncio
async def test_bash_read_only_detection():
    bash = BashTool()
    assert bash.is_read_only(bash.input_model(command="ls"))
    assert bash.is_read_only(bash.input_model(command="git diff"))
    assert not bash.is_read_only(bash.input_model(command="rm file.txt"))


@pytest.mark.asyncio
async def test_bash_timeout():
    bash = BashTool()
    ctx = ToolContext(cwd=os.getcwd())
    result = await bash.call(
        bash.input_model(command='python -c "import time; time.sleep(5)"', timeout=1),
        ctx,
    )
    assert not result.success
    assert "timed out" in result.error.lower()


@pytest.mark.asyncio
async def test_bash_failure():
    bash = BashTool()
    ctx = ToolContext(cwd=os.getcwd())
    # Use a command that fails on both Windows and Unix
    result = await bash.call(bash.input_model(command="exit 1"), ctx)
    assert not result.success
    assert "1" in result.error


@pytest.mark.asyncio
async def test_bash_cwd(tmp_path):
    bash = BashTool()
    ctx = ToolContext(cwd=str(tmp_path))
    result = await bash.call(bash.input_model(command="pwd" if os.name != "nt" else "cd"), ctx)
    assert result.success
