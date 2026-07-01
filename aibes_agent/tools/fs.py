import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from aibes_agent.tools.base import Tool, ToolContext, ToolResult


class FileReadInput(BaseModel):
    file_path: str = Field(..., description="Absolute path to the file to read")
    offset: int = Field(1, description="Line number to start from (1-indexed)")
    limit: int = Field(500, description="Maximum number of lines to read")


class FileReadTool(Tool[FileReadInput]):
    name = "FileRead"
    description = (
        "Read a text file from the local filesystem. Supports offset and limit for large files."
    )
    input_model = FileReadInput

    def is_read_only(self, input: FileReadInput) -> bool:
        return True

    async def call(self, input: FileReadInput, context: ToolContext) -> ToolResult:
        path = Path(input.file_path).expanduser().resolve()
        if not path.exists():
            return ToolResult.fail(f"File not found: {path}")
        if not path.is_file():
            return ToolResult.fail(f"Not a file: {path}")

        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            total = len(lines)
            start = max(0, input.offset - 1)
            end = start + input.limit
            selected = lines[start:end]
            content = "".join(selected)
            return ToolResult.ok(
                content,
                file_path=str(path),
                total_lines=total,
                offset=input.offset,
                limit=input.limit,
                returned_lines=len(selected),
            )
        except Exception as e:
            return ToolResult.fail(f"Failed to read {path}: {e}")


class FileWriteInput(BaseModel):
    file_path: str = Field(..., description="Absolute path to the file to write")
    content: str = Field(..., description="Content to write to the file")


class FileWriteTool(Tool[FileWriteInput]):
    name = "FileWrite"
    description = "Create or overwrite a file in the local filesystem."
    input_model = FileWriteInput

    def is_read_only(self, input: FileWriteInput) -> bool:
        return False

    async def call(self, input: FileWriteInput, context: ToolContext) -> ToolResult:
        path = Path(input.file_path).expanduser().resolve()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            existed = path.exists()
            with open(path, "w", encoding="utf-8") as f:
                f.write(input.content)
            action = "updated" if existed else "created"
            return ToolResult.ok(
                f"File {action}: {path}",
                file_path=str(path),
                action=action,
            )
        except Exception as e:
            return ToolResult.fail(f"Failed to write {path}: {e}")


class FileEditInput(BaseModel):
    file_path: str = Field(..., description="Absolute path to the file to edit")
    old_string: str = Field(..., description="Exact string to replace")
    new_string: str = Field(..., description="Replacement string")


class FileEditTool(Tool[FileEditInput]):
    name = "FileEdit"
    description = "Make a precise edit to a file by replacing old_string with new_string."
    input_model = FileEditInput

    def is_read_only(self, input: FileEditInput) -> bool:
        return False

    async def call(self, input: FileEditInput, context: ToolContext) -> ToolResult:
        path = Path(input.file_path).expanduser().resolve()
        if not path.exists():
            return ToolResult.fail(f"File not found: {path}")
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            if input.old_string not in content:
                return ToolResult.fail(f"old_string not found in {path}")
            content = content.replace(input.old_string, input.new_string, 1)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return ToolResult.ok(
                f"Edited {path}",
                file_path=str(path),
            )
        except Exception as e:
            return ToolResult.fail(f"Failed to edit {path}: {e}")
