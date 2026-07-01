from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from minagent.tools.base import ToolContext


@dataclass
class PermissionRule:
    action: str  # allow, deny, ask
    resource_type: str  # filesystem, shell, tool
    pattern: str


class PermissionEngine:
    """权限规则引擎。"""

    def __init__(self, rules: Optional[List[PermissionRule]] = None, mode: str = "auto"):
        self.rules = rules or []
        self.mode = mode  # ask, auto, full_auto

    @staticmethod
    def default() -> "PermissionEngine":
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
        )

    async def check(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        context: ToolContext,
    ) -> bool:
        """检查是否允许执行工具。简化版：auto 模式下只校验基础规则。"""
        if self.mode == "full_auto":
            return True
        if self.mode == "ask":
            # 演示模式：自动允许，真实场景应询问用户
            return True

        # auto 模式：先匹配 tool 级别规则
        for rule in reversed(self.rules):
            if rule.resource_type == "tool":
                if fnmatch.fnmatch(tool_name, rule.pattern):
                    if rule.action == "deny":
                        return False
                    if rule.action == "allow":
                        return True
                    if rule.action == "ask":
                        # 简化：自动允许；生产环境应弹窗
                        return True

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

        return True

    @staticmethod
    def _match_path(rule_pattern: str, target_path: str) -> bool:
        """支持 ** 通配的路径匹配。"""
        normalized = str(Path(target_path).expanduser().resolve())
        # 简单转换为 regex
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
