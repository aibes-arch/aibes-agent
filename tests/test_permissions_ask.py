import os

import pytest

from aibes_agent.permissions.engine import PermissionEngine, PermissionRule, cli_ask_callback
from aibes_agent.tools.base import ToolContext


@pytest.fixture
def ctx():
    return ToolContext(cwd="/tmp")


@pytest.mark.asyncio
async def test_ask_callback_denies(ctx):
    async def deny(_msg):
        return False

    engine = PermissionEngine(
        rules=[PermissionRule("ask", "tool", "Bash")],
        mode="auto",
        on_ask=deny,
    )
    assert not await engine.check("Bash", {"command": "ls"}, ctx)


@pytest.mark.asyncio
async def test_ask_callback_allows(ctx):
    async def allow(_msg):
        return True

    engine = PermissionEngine(
        rules=[PermissionRule("ask", "tool", "Bash")],
        mode="auto",
        on_ask=allow,
    )
    assert await engine.check("Bash", {"command": "ls"}, ctx)


@pytest.mark.asyncio
async def test_mode_ask_uses_callback(ctx):
    async def allow(_msg):
        return True

    engine = PermissionEngine(mode="ask", on_ask=allow)
    assert await engine.check("Anything", {}, ctx)


@pytest.mark.asyncio
async def test_default_without_callback_auto_allows(ctx):
    engine = PermissionEngine.default()
    assert await engine.check("Bash", {"command": "ls"}, ctx)


@pytest.mark.asyncio
async def test_yes_to_all_env(ctx, monkeypatch):
    monkeypatch.setenv("AIBES_AGENT_YES_TO_ALL", "1")
    engine = PermissionEngine.default()
    assert await engine.check("Bash", {"command": "rm -rf /"}, ctx)


@pytest.mark.asyncio
async def test_cli_ask_callback_simulated_input(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _msg: "y")
    result = await cli_ask_callback("Allow Bash?")
    assert result is True


@pytest.mark.asyncio
async def test_cli_ask_callback_simulated_no(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _msg: "n")
    result = await cli_ask_callback("Allow Bash?")
    assert result is False
