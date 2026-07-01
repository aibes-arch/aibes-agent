from __future__ import annotations

from pydantic import BaseModel, Field

from minagent.tools.base import Tool, ToolContext, ToolResult


class TaskListInput(BaseModel):
    action: str = Field("list", description="list, add, or done")
    task: str = Field("", description="Task description (for add/done)")
    task_id: int = Field(-1, description="Task index (for done)")


class TaskListTool(Tool):
    name = "TaskList"
    description = "Manage a simple task list. Actions: list, add, done."
    input_model = TaskListInput

    def is_read_only(self, input: TaskListInput) -> bool:
        return input.action == "list"

    async def call(self, input: TaskListInput, context: ToolContext) -> ToolResult:
        tasks = context.get("tasks", [])

        if input.action == "list":
            if not tasks:
                return ToolResult.ok("No tasks yet.")
            lines = []
            for i, (desc, done) in enumerate(tasks):
                status = "✅" if done else "⬜"
                lines.append(f"{i}. {status} {desc}")
            return ToolResult.ok("\n".join(lines))

        elif input.action == "add":
            if not input.task:
                return ToolResult.fail("Task description required")
            tasks.append([input.task, False])
            context.set("tasks", tasks)
            return ToolResult.ok(f"Added task: {input.task}")

        elif input.action == "done":
            if input.task_id < 0 or input.task_id >= len(tasks):
                return ToolResult.fail(f"Invalid task id: {input.task_id}")
            desc, _ = tasks[input.task_id]
            tasks[input.task_id] = [desc, True]
            context.set("tasks", tasks)
            return ToolResult.ok(f"Marked task {input.task_id} as done: {desc}")

        return ToolResult.fail(f"Unknown action: {input.action}")
