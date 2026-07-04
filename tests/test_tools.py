import os

import pytest

from aibes_agent.tools.base import ToolContext
from aibes_agent.tools.fs import FileReadTool, FileWriteTool, FileEditTool
from aibes_agent.tools.images import ImageReadTool
from aibes_agent.tools.shell import BashTool
from aibes_agent.tools.search import GlobTool
from aibes_agent.tools.task import TaskListTool


@pytest.fixture
def tmp_path(tmp_path):
    return tmp_path


@pytest.mark.asyncio
async def test_file_read_write(tmp_path):
    read_tool = FileReadTool()
    write_tool = FileWriteTool()
    ctx = ToolContext(cwd=str(tmp_path))

    test_file = tmp_path / "test.txt"
    result = await write_tool.call(
        write_tool.input_model(file_path=str(test_file), content="hello world"),
        ctx,
    )
    assert result.success

    result = await read_tool.call(
        read_tool.input_model(file_path=str(test_file)),
        ctx,
    )
    assert result.success
    assert "hello world" in result.content


@pytest.mark.asyncio
async def test_file_edit(tmp_path):
    edit_tool = FileEditTool()
    write_tool = FileWriteTool()
    ctx = ToolContext(cwd=str(tmp_path))

    test_file = tmp_path / "edit.txt"
    await write_tool.call(
        write_tool.input_model(file_path=str(test_file), content="foo bar baz"),
        ctx,
    )
    result = await edit_tool.call(
        edit_tool.input_model(
            file_path=str(test_file),
            old_string="bar",
            new_string="qux",
        ),
        ctx,
    )
    assert result.success

    read_tool = FileReadTool()
    result = await read_tool.call(
        read_tool.input_model(file_path=str(test_file)),
        ctx,
    )
    assert "foo qux baz" in result.content


@pytest.mark.asyncio
async def test_bash_read_only():
    bash = BashTool()
    ctx = ToolContext(cwd=os.getcwd())
    result = await bash.call(
        bash.input_model(command="echo core"),
        ctx,
    )
    assert result.success
    assert "core" in result.content


@pytest.mark.asyncio
async def test_glob():
    glob = GlobTool()
    ctx = ToolContext(cwd=os.getcwd())
    result = await glob.call(
        glob.input_model(pattern="**/*.py"),
        ctx,
    )
    assert result.success
    assert len(result.content) > 0


@pytest.mark.asyncio
async def test_task_list():
    task = TaskListTool()
    ctx = ToolContext(cwd=os.getcwd())
    await task.call(task.input_model(action="add", task="read docs"), ctx)
    await task.call(task.input_model(action="add", task="write code"), ctx)
    await task.call(task.input_model(action="done", task_id=0), ctx)
    result = await task.call(task.input_model(action="list"), ctx)
    assert "✅ [0] read docs" in result.content
    assert "⬜ [1] write code" in result.content


@pytest.mark.asyncio
async def test_image_read_metadata(tmp_path):
    from PIL import Image

    img_path = tmp_path / "test.png"
    img = Image.new("RGB", (100, 50), color="red")
    img.save(img_path)

    tool = ImageReadTool()
    ctx = ToolContext(cwd=str(tmp_path))
    result = await tool.call(
        tool.input_model(file_path=str(img_path)),
        ctx,
    )
    assert result.success
    assert "100x50" in result.content
    assert result.metadata["width"] == 100
    assert result.metadata["height"] == 50
    assert result.metadata["format"] == "PNG"


@pytest.mark.asyncio
async def test_image_read_not_found(tmp_path):
    tool = ImageReadTool()
    ctx = ToolContext(cwd=str(tmp_path))
    result = await tool.call(
        tool.input_model(file_path="missing.jpg"),
        ctx,
    )
    assert not result.success
    assert "File not found" in result.error
