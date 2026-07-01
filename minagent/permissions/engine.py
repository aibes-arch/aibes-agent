from __future__ import annotations

import asyncio
import fnmatch
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

from minagent.tools.base import ToolContext

OnAskCallback = Callable[[str], Awaitable[bool]]


async def cli_ask_callback(message: str) -> bool:
    """命令行交互式权限确认回调。"""

    def _prompt() -> bool:
        try:
            answer = input(f"{message} [y/N]: ").strip().lower()
            return answer in ("y", "yes")
        except (EOFError, KeyboardInterrupt):
            return False

    return await asyncio.to_thread(_prompt)


async def _auto_yes_callback(_message: str) -> bool:
    return True


@dataclass
class PermissionRule:
    action: str  # allow, deny, ask
    resource_type: str  # filesystem, shell, tool
    pattern: str


class PermissionEngine:
    """权限规则引擎。"""

    def __init__(
        self,
        rules: Optional[List[PermissionRule]] = None,
        mode: str = "auto",
        on_ask: Optional[OnAskCallback] = None,
    ):
        self.rules = rules or []
        self.mode = mode  # ask, auto, full_auto
        self.on_ask = on_ask

    @staticmethod
    def default(
        on_ask: Optional[OnAskCallback] = None,
        interactive: bool = False,
    ) -> "PermissionEngine":
        # 如果命令行传了 --yes-to-all，自动通过所有 ask
        if on_ask is None and os.getenv("MINAGENT_YES_TO_ALL"):
            on_ask = _auto_yes_callback
        # 显式要求交互式时，使用命令行提示
        if on_ask is None and interactive:
            on_ask = cli_ask_callback
        return PermissionEngine(
            rules=[
                PermissionRule("allow", "tool", "FileRead"),
                PermissionRule("allow", "tool", "Grep"),
                PermissionRule("allow", "tool", "Glob"),
                PermissionRule("ask", "tool", "FileWrite"),
                PermissionRule("ask", "tool", "FileEdit"),
                PermissionRule("ask", "tool", "Bash"),
                PermissionRule("ask", "tool", "TaskList"),
            ],
            mode="auto",
            on_ask=on_ask,
        )

    def _ask_message(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """生成询问用户的消息。"""
        parts = [f"Allow tool '{tool_name}'?"]
        if arguments:
            args_str = ", ".join(f"{k}={v!r}" for k, v in arguments.items())
            parts.append(f"Arguments: {args_str}")
        return " ".join(parts)

    async def _ask(self, message: str) -> bool:
        """询问用户，没有回调时默认允许。"""
        if self.on_ask is None:
            return True
        try:
            return await self.on_ask(message)
        except Exception:
            return False

    async def check(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        context: ToolContext,
    ) -> bool:
        """检查是否允许执行工具。"""
        if self.mode == "full_auto":
            return True

        message = self._ask_message(tool_name, arguments)

        if self.mode == "ask":
            return await self._ask(message)

        # auto 模式：先匹配 tool 级别规则
        for rule in reversed(self.rules):
            if rule.resource_type == "tool":
                if fnmatch.fnmatch(tool_name, rule.pattern):
                    if rule.action == "deny":
                        return False
                    if rule.action == "allow":
                        return True
                    if rule.action == "ask":
                        return await self._ask(message)

        # 文件系统规则
        file_path = arguments.get("file_path") or arguments.get("path") or ""
        if file_path:
            for rule in reversed(self.rules):
                if rule.resource_type == "filesystem":
                    if self._match_path(rule.pattern, file_path):
                        if rule.action == "deny":
                            return False
                        if rule.action == "allow":
                            return True
                        if rule.action == "ask":
                            return await self._ask(f"Allow filesystem access to '{file_path}'?")

        # shell 规则
        command = arguments.get("command", "")
        if command:
            for rule in reversed(self.rules):
                if rule.resource_type == "shell":
                    if re.match(rule.pattern, command):
                        if rule.action == "deny":
                            return False
                        if rule.action == "allow":
                            return True
                        if rule.action == "ask":
                            return await self._ask(f"Allow shell command: {command!r}?")

        return True

    @staticmethod
    def _match_path(rule_pattern: str, target_path: str) -> bool:
        """支持 ** 通配的路径匹配。"""
        normalized = str(Path(target_path).expanduser().resolve())
        pattern = rule_pattern
        if pattern.endswith("/**"):
            prefix = pattern[:-3]
            return normalized.startswith(prefix)
        if pattern.endswith("/*"):
            prefix = pattern[:-2]
            return normalized.startswith(prefix)
        return fnmatch.fnmatch(normalized, pattern)

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "PermissionEngine":
        rules = []
        mode = config.get("mode", "auto")
        for rule in config.get("rules", []):
            rules.append(
                PermissionRule(
                    action=rule["action"],
                    resource_type=rule["resource_type"],
                    pattern=rule["pattern"],
                )
            )
        return cls(rules=rules, mode=mode)
