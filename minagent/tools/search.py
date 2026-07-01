import asyncio
import json
import shutil
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field

from minagent.tools.base import Tool, ToolContext, ToolResult


class GrepInput(BaseModel):
    pattern: str = Field(..., description="Regular expression pattern to search for")
    path: str = Field("", description="File or directory to search in")
    glob: str = Field("", description="Glob pattern to filter files (e.g. '*.py')")
    output_mode: str = Field(
        "files_with_matches", description="files_with_matches, content, or count"
    )
    head_limit: int = Field(250, description="Limit number of results")


class GrepTool(Tool):
    name = "Grep"
    description = "Search file contents using ripgrep (rg)."
    input_model = GrepInput

    def is_read_only(self, input: GrepInput) -> bool:
        return True

    async def call(self, input: GrepInput, context: ToolContext) -> ToolResult:
        rg = shutil.which("rg")
        if not rg:
            return ToolResult.fail("ripgrep (rg) not found in PATH")

        search_path = input.path or context.cwd
        cmd = [rg, "--json", input.pattern, search_path]
        if input.glob:
            cmd.extend(["--glob", input.glob])

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            err = stderr.decode("utf-8", errors="replace")
            if proc.returncode not in (0, 1):
                return ToolResult.fail(f"rg failed: {err}")

            files = set()
            lines = []
            for line in stdout.decode("utf-8", errors="replace").strip().split("\n"):
                if not line:
                    continue
                try:
                    import json

                    data = json.loads(line)
                    if data.get("type") == "match":
                        path = data.get("data", {}).get("path", {}).get("text", "")
                        text = data.get("data", {}).get("lines", {}).get("text", "")
                        files.add(path)
                        lines.append(f"{path}: {text.strip()}")
                except Exception:
                    pass

            if input.output_mode == "files_with_matches":
                result = "\n".join(sorted(files)[: input.head_limit])
            elif input.output_mode == "count":
                result = f"Matches: {len(lines)} files: {len(files)}"
            else:
                result = "\n".join(lines[: input.head_limit])

            return ToolResult.ok(result or "No matches found")
        except Exception as e:
            return ToolResult.fail(f"Grep failed: {e}")


class GlobInput(BaseModel):
    pattern: str = Field(..., description="Glob pattern to list files")
    path: str = Field("", description="Directory to search in")


class GlobTool(Tool):
    name = "Glob"
    description = "List files matching a glob pattern."
    input_model = GlobInput

    def is_read_only(self, input: GlobInput) -> bool:
        return True

    async def call(self, input: GlobInput, context: ToolContext) -> ToolResult:
        import fnmatch
        import os

        raw_base = input.path or context.cwd
        # Convert MSYS /c/path to C:/path on Windows
        if os.name == "nt" and raw_base.startswith("/"):
            parts = raw_base.strip("/").split("/", 1)
            if len(parts) == 2 and len(parts[0]) == 1:
                raw_base = f"{parts[0].upper()}:/" + parts[1]

        base = Path(raw_base).expanduser().resolve()
        matches = []
        for root, dirs, files in os.walk(base):
            # 跳过隐藏目录和 __pycache__
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
            for f in files:
                if not f.startswith(".") and fnmatch.fnmatch(f, Path(input.pattern).name):
                    matches.append(str(Path(root) / f))
        return ToolResult.ok("\n".join(matches[:250]))
