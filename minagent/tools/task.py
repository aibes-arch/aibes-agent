"""增强版任务列表工具。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from minagent.tools.base import Tool, ToolContext, ToolResult


@dataclass
class Task:
    """任务项。"""

    id: int
    description: str
    status: str = "pending"  # pending / in_progress / done / failed
    parent_id: Optional[int] = None
    dependencies: List[int] = field(default_factory=list)
    progress: int = 0  # 0-100
    result: str = ""


class TaskListInput(BaseModel):
    """TaskListTool 输入。"""

    action: str = Field(
        "list",
        description="One of: list, add, add_subtask, start, done, fail, set_progress",
    )
    task: str = Field("", description="Task description (for add/add_subtask)")
    task_id: int = Field(-1, description="Task index (for start/done/fail/set_progress)")
    parent_id: int = Field(-1, description="Parent task id (for add_subtask)")
    dependencies: List[int] = Field(
        default_factory=list,
        description="List of task ids that must be completed first",
    )
    progress: int = Field(0, description="Progress percentage 0-100")


class TaskListTool(Tool[TaskListInput]):
    """管理支持子任务、依赖和进度的任务列表。"""

    name = "TaskList"
    description = (
        "Manage a hierarchical task list with dependencies and progress. "
        "Actions: list, add, add_subtask, start, done, fail, set_progress."
    )
    input_model = TaskListInput

    def _get_tasks(self, context: ToolContext) -> List[Task]:
        return context.get("tasks_v2", [])

    def _save_tasks(self, context: ToolContext, tasks: List[Task]) -> None:
        context.set("tasks_v2", tasks)

    def _find_task(self, tasks: List[Task], task_id: int) -> Optional[Task]:
        for t in tasks:
            if t.id == task_id:
                return t
        return None

    def _next_id(self, tasks: List[Task]) -> int:
        return max((t.id for t in tasks), default=-1) + 1

    def _render_tasks(self, tasks: List[Task]) -> str:
        if not tasks:
            return "No tasks yet."

        # 按 parent_id 构建层级
        roots = [t for t in tasks if t.parent_id is None]
        lines: List[str] = []

        def icon(status: str) -> str:
            return {
                "pending": "⬜",
                "in_progress": "🔄",
                "done": "✅",
                "failed": "❌",
            }.get(status, "⬜")

        def render(task: Task, indent: int = 0) -> None:
            prefix = "  " * indent
            progress = f" ({task.progress}%)" if task.progress > 0 and task.status != "done" else ""
            lines.append(f"{prefix}{icon(task.status)} [{task.id}] {task.description}{progress}")
            for child in tasks:
                if child.parent_id == task.id:
                    render(child, indent + 1)

        for root in roots:
            render(root)

        return "\n".join(lines)

    def is_read_only(self, input: TaskListInput) -> bool:
        return input.action == "list"

    async def call(self, input: TaskListInput, context: ToolContext) -> ToolResult:
        tasks = self._get_tasks(context)

        if input.action == "list":
            return ToolResult.ok(self._render_tasks(tasks))

        if input.action == "add":
            if not input.task:
                return ToolResult.fail("Task description required")
            new_task = Task(
                id=self._next_id(tasks),
                description=input.task,
                dependencies=input.dependencies,
            )
            tasks.append(new_task)
            self._save_tasks(context, tasks)
            return ToolResult.ok(f"Added task [{new_task.id}]: {new_task.description}")

        if input.action == "add_subtask":
            if not input.task:
                return ToolResult.fail("Task description required")
            if input.parent_id < 0:
                return ToolResult.fail("parent_id required for add_subtask")
            parent = self._find_task(tasks, input.parent_id)
            if parent is None:
                return ToolResult.fail(f"Parent task {input.parent_id} not found")
            new_task = Task(
                id=self._next_id(tasks),
                description=input.task,
                parent_id=input.parent_id,
                dependencies=input.dependencies,
            )
            tasks.append(new_task)
            self._save_tasks(context, tasks)
            return ToolResult.ok(
                f"Added subtask [{new_task.id}] under [{parent.id}]: {new_task.description}"
            )

        # 以下操作需要 task_id
        if input.task_id < 0:
            return ToolResult.fail("task_id required")
        task = self._find_task(tasks, input.task_id)
        if task is None:
            return ToolResult.fail(f"Task {input.task_id} not found")

        if input.action == "start":
            task.status = "in_progress"
            self._save_tasks(context, tasks)
            return ToolResult.ok(f"Started task [{task.id}]: {task.description}")

        if input.action == "done":
            # 检查依赖
            for dep_id in task.dependencies:
                dep = self._find_task(tasks, dep_id)
                if dep is None or dep.status != "done":
                    return ToolResult.fail(
                        f"Cannot complete task [{task.id}] because dependency [{dep_id}] is not done"
                    )
            task.status = "done"
            task.progress = 100
            self._save_tasks(context, tasks)
            return ToolResult.ok(f"Completed task [{task.id}]: {task.description}")

        if input.action == "fail":
            task.status = "failed"
            self._save_tasks(context, tasks)
            return ToolResult.ok(f"Marked task [{task.id}] as failed: {task.description}")

        if input.action == "set_progress":
            task.progress = max(0, min(100, input.progress))
            if task.progress > 0 and task.status == "pending":
                task.status = "in_progress"
            if task.progress == 100 and task.status != "done":
                task.status = "in_progress"
            self._save_tasks(context, tasks)
            return ToolResult.ok(f"Set task [{task.id}] progress to {task.progress}%")

        return ToolResult.fail(f"Unknown action: {input.action}")
