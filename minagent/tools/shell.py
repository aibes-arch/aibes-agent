import asyncio
import shutil
from pathlib import Path
from typing import List

from pydantic import BaseModel, Field

from minagent.tools.base import Tool, ToolContext, ToolResult


class BashInput(BaseModel):
    command: str = Field(..., description="Shell command to execute")
    timeout: int = Field(60, description="Timeout in seconds")
    cwd: str = Field("", description="Working directory (empty = use agent cwd)")


class BashTool(Tool[BashInput]):
    name = "Bash"
    description = "Execute a shell command. Use for git, testing, builds, file listing, and other shell operations."
    input_model = BashInput

    def is_read_only(self, input: BashInput) -> bool:
        # 简化：把 ls/find/grep/cat 等常见只读命令视为只读
        read_only_prefixes = (
            "ls",
            "find",
            "grep",
            "cat",
            "head",
            "tail",
            "wc",
            "echo",
            "git status",
            "git log",
            "git diff",
        )
        cmd = input.command.strip()
        return any(cmd.startswith(p) for p in read_only_prefixes)

    async def call(self, input: BashInput, context: ToolContext) -> ToolResult:
        cwd = input.cwd or context.cwd
        # Windows 需要 cwd 是原生路径
        import sys

        if sys.platform == "win32" and cwd.startswith("/c/"):
            cwd = cwd.replace("/c/", "C:\\/", 1)
        try:
            proc = await asyncio.create_subprocess_shell(
                input.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=input.timeout)
            except asyncio.TimeoutError:
                proc.kill()
                return ToolResult.fail(f"Command timed out after {input.timeout}s")

            out = stdout.decode("utf-8", errors="replace")
            err = stderr.decode("utf-8", errors="replace")
            if proc.returncode != 0:
                content = out
                if err:
                    content += f"\nSTDERR:\n{err}"
                return ToolResult.fail(f"Exit code {proc.returncode}", content=content.strip())
            content = out
            if err:
                content += f"\nSTDERR:\n{err}"
            return ToolResult.ok(content.strip())
        except Exception as e:
            return ToolResult.fail(f"Failed to execute command: {e}")
