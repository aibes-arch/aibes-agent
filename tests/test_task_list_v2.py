import pytest

from aibes_agent.tools.base import ToolContext
from aibes_agent.tools.task import TaskListTool


@pytest.fixture
def ctx():
    return ToolContext(cwd="/tmp")


@pytest.mark.asyncio
async def test_task_list_add_and_list(ctx):
    tool = TaskListTool()
    await tool.call(tool.input_model(action="add", task="read docs"), ctx)
    await tool.call(tool.input_model(action="add", task="write code"), ctx)
    result = await tool.call(tool.input_model(action="list"), ctx)
    assert result.success
    assert "read docs" in result.content
    assert "write code" in result.content


@pytest.mark.asyncio
async def test_task_list_subtask(ctx):
    tool = TaskListTool()
    await tool.call(tool.input_model(action="add", task="parent"), ctx)
    await tool.call(
        tool.input_model(action="add_subtask", task="child", parent_id=0),
        ctx,
    )
    result = await tool.call(tool.input_model(action="list"), ctx)
    assert "parent" in result.content
    assert "child" in result.content


@pytest.mark.asyncio
async def test_task_list_dependencies(ctx):
    tool = TaskListTool()
    await tool.call(tool.input_model(action="add", task="step1"), ctx)
    await tool.call(
        tool.input_model(action="add", task="step2", dependencies=[0]),
        ctx,
    )

    # step2 不能先完成
    result = await tool.call(tool.input_model(action="done", task_id=1), ctx)
    assert not result.success
    assert "dependency" in (result.error or result.content)

    await tool.call(tool.input_model(action="done", task_id=0), ctx)
    result = await tool.call(tool.input_model(action="done", task_id=1), ctx)
    assert result.success


@pytest.mark.asyncio
async def test_task_list_progress(ctx):
    tool = TaskListTool()
    await tool.call(tool.input_model(action="add", task="work"), ctx)
    result = await tool.call(
        tool.input_model(action="set_progress", task_id=0, progress=50),
        ctx,
    )
    assert result.success
    result = await tool.call(tool.input_model(action="list"), ctx)
    assert "50%" in result.content
