import os
from pathlib import Path

import pytest

from aibes_agent.permissions.engine import PermissionEngine, PermissionRule
from aibes_agent.tools.base import ToolContext


@pytest.fixture
def ctx(tmp_path):
    return ToolContext(cwd=str(tmp_path))


@pytest.mark.asyncio
async def test_allow_tool(ctx):
    engine = PermissionEngine(
        rules=[PermissionRule("allow", "tool", "FileRead")],
        mode="auto",
    )
    assert await engine.check("FileRead", {"file_path": "/etc/passwd"}, ctx)


@pytest.mark.asyncio
async def test_deny_tool(ctx):
    engine = PermissionEngine(
        rules=[PermissionRule("deny", "tool", "FileWrite")],
        mode="auto",
    )
    assert not await engine.check("FileWrite", {"file_path": "/etc/passwd"}, ctx)


@pytest.mark.asyncio
async def test_default_allows_read_tools(ctx):
    engine = PermissionEngine.default()
    assert await engine.check("FileRead", {"file_path": "x.txt"}, ctx)
    assert await engine.check("Grep", {"pattern": "foo"}, ctx)
    assert await engine.check("Glob", {"pattern": "*.py"}, ctx)


@pytest.mark.asyncio
async def test_default_asks_write_tools(ctx):
    engine = PermissionEngine.default()
    # auto 模式下，默认规则对 FileWrite 是 ask，但 on_ask 为 None 时默认允许
    assert await engine.check("FileWrite", {"file_path": "x.txt"}, ctx)


@pytest.mark.asyncio
async def test_ask_mode_with_callback(ctx):
    async def _yes(_):
        return True

    engine = PermissionEngine(
        rules=[PermissionRule("ask", "tool", "Bash")],
        mode="ask",
        on_ask=_yes,
    )
    assert await engine.check("Bash", {"command": "ls"}, ctx)


@pytest.mark.asyncio
async def test_ask_mode_callback_denies(ctx):
    engine = PermissionEngine(
        rules=[PermissionRule("ask", "tool", "Bash")],
        mode="ask",
        on_ask=lambda _: False,
    )
    assert not await engine.check("Bash", {"command": "ls"}, ctx)


@pytest.mark.asyncio
async def test_full_auto(ctx):
    engine = PermissionEngine(rules=[], mode="full_auto")
    assert await engine.check("Bash", {"command": "rm -rf /"}, ctx)


@pytest.mark.asyncio
async def test_filesystem_allow_path(ctx, tmp_path):
    engine = PermissionEngine(
        rules=[
            PermissionRule("allow", "tool", "FileRead"),
            PermissionRule("allow", "filesystem", str(tmp_path / "**")),
        ],
        mode="auto",
    )
    assert await engine.check("FileRead", {"file_path": str(tmp_path / "allowed.txt")}, ctx)


@pytest.mark.asyncio
async def test_filesystem_deny_path(ctx, tmp_path):
    # Tool-level rules take precedence; omit tool allow to test filesystem deny
    denied = tmp_path / "secret" / "file.txt"
    denied.parent.mkdir()
    denied.write_text("secret", encoding="utf-8")
    engine = PermissionEngine(
        rules=[
            PermissionRule("deny", "filesystem", str(tmp_path / "secret" / "**")),
        ],
        mode="auto",
    )
    assert not await engine.check("FileRead", {"file_path": str(denied)}, ctx)


@pytest.mark.asyncio
async def test_shell_allow_pattern(ctx):
    # Omit tool-level Bash allow so shell rules are evaluated
    # Rules are evaluated in reverse order; place allow after deny so allow wins
    engine = PermissionEngine(
        rules=[
            PermissionRule("deny", "shell", ".*"),
            PermissionRule("allow", "shell", "^git .*"),
        ],
        mode="auto",
    )
    assert await engine.check("Bash", {"command": "git status"}, ctx)
    assert not await engine.check("Bash", {"command": "rm -rf /"}, ctx)


@pytest.mark.asyncio
async def test_shell_unmatched_allowed_by_default(ctx):
    engine = PermissionEngine(
        rules=[],
        mode="auto",
    )
    # No shell rules means unmatched commands are allowed
    assert await engine.check("Bash", {"command": "anything"}, ctx)


@pytest.mark.asyncio
async def test_order_reversed(ctx):
    engine = PermissionEngine(
        rules=[
            PermissionRule("allow", "tool", "Bash"),
            PermissionRule("deny", "tool", "Bash"),
        ],
        mode="auto",
    )
    assert not await engine.check("Bash", {"command": "ls"}, ctx)


@pytest.mark.asyncio
async def test_from_config(ctx):
    engine = PermissionEngine.from_config(
        {
            "mode": "auto",
            "rules": [
                {"action": "allow", "resource_type": "tool", "pattern": "FileRead"},
            ],
        }
    )
    assert await engine.check("FileRead", {}, ctx)


def test_default_respects_env_var(monkeypatch):
    monkeypatch.setenv("AIBES_AGENT_YES_TO_ALL", "1")
    engine = PermissionEngine.default()
    assert engine.on_ask is not None


def test_match_path_prefix(tmp_path):
    engine = PermissionEngine()
    base = str(tmp_path)
    assert engine._match_path(f"{base}/**", f"{base}/sub/file.txt")
    assert engine._match_path(f"{base}/*", f"{base}/file.txt")
    assert not engine._match_path(f"{base}/**", "/other/path")
