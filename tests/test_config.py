import os

import pytest

from aibes_agent.config import (
    MCPConfig,
    MCPServerConfig,
    MinagentConfig,
    RouterRule,
    WebConfig,
)


def test_default_config():
    cfg = MinagentConfig()
    assert cfg.llm.model is None
    assert cfg.permissions.mode == "auto"
    assert cfg.skills.auto_load is True
    assert cfg.web.port == 8000


def test_from_dict_full():
    data = {
        "llm": {
            "base_url": "http://localhost:1234/v1",
            "api_key": "dummy",
            "model": "qwen/test",
            "timeout": 60.0,
            "max_retries": 3,
            "retry_delay": 2.0,
        },
        "router": {
            "default": "qwen/test",
            "rules": [
                {"pattern": "^write.*", "model": "qwen/coder"},
            ],
        },
        "permissions": {
            "mode": "ask",
            "rules": [
                {"action": "allow", "resource_type": "tool", "pattern": "FileRead"},
            ],
        },
        "skills": {
            "auto_load": False,
            "paths": ["./skills"],
        },
        "mcp_servers": {
            "fs": {
                "transport": "stdio",
                "command": "npx",
                "args": ["-y", "server-fs"],
                "env": {"KEY": "val"},
            },
            "remote": {
                "transport": "sse",
                "url": "http://localhost:8080/sse",
            },
        },
        "session": {"store": "file", "path": ".sessions"},
        "web": {"host": "0.0.0.0", "port": 9000},
    }
    cfg = MinagentConfig.from_dict(data)
    assert cfg.llm.base_url == "http://localhost:1234/v1"
    assert cfg.llm.model == "qwen/test"
    assert cfg.llm.timeout == 60.0
    assert cfg.router.default == "qwen/test"
    assert cfg.router.rules == [RouterRule(pattern="^write.*", model="qwen/coder")]
    assert cfg.permissions.mode == "ask"
    assert cfg.permissions.rules[0]["action"] == "allow"
    assert cfg.skills.auto_load is False
    assert cfg.skills.paths == ["./skills"]
    assert cfg.mcp_servers["fs"].transport == "stdio"
    assert cfg.mcp_servers["fs"].env == {"KEY": "val"}
    assert cfg.mcp_servers["remote"].url == "http://localhost:8080/sse"
    assert cfg.session.path == ".sessions"
    assert cfg.web == WebConfig(host="0.0.0.0", port=9000)


def test_load_from_file(tmp_path, monkeypatch):
    config_file = tmp_path / "aibes-agent.yaml"
    config_file.write_text(
        """
llm:
  model: test-model
web:
  port: 7777
""",
        encoding="utf-8",
    )
    cfg = MinagentConfig.load(str(config_file))
    assert cfg.llm.model == "test-model"
    assert cfg.web.port == 7777


def test_load_searches_default(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    default_file = tmp_path / ".aibes-agent" / "config.yaml"
    default_file.parent.mkdir(parents=True)
    default_file.write_text("web:\n  port: 8888\n", encoding="utf-8")
    cfg = MinagentConfig.load()
    assert cfg.web.port == 8888


def test_env_overrides(tmp_path, monkeypatch):
    config_file = tmp_path / "aibes-agent.yaml"
    config_file.write_text("llm:\n  model: yaml-model\n", encoding="utf-8")
    monkeypatch.setenv("AIBES_AGENT_MODEL", "env-model")
    cfg = MinagentConfig.load(str(config_file))
    assert cfg.llm.model == "env-model"


def test_config_to_runtime_objects(tmp_path):
    cfg = MinagentConfig.from_dict(
        {
            "llm": {"base_url": "http://localhost/v1", "model": "m"},
            "permissions": {
                "rules": [{"action": "allow", "resource_type": "tool", "pattern": "Glob"}]
            },
            "session": {"path": str(tmp_path / "sessions")},
        }
    )
    llm = cfg.to_llm_client()
    assert llm.base_url == "http://localhost/v1"
    assert llm.model == "m"
    perm = cfg.to_permission_engine()
    assert perm.mode == "auto"
    store = cfg.to_session_store()
    assert store.directory == tmp_path / "sessions"


def test_mcp_server_config_defaults():
    cfg = MCPServerConfig()
    assert cfg.transport == "stdio"
    assert cfg.args == []


def test_mcp_config_defaults():
    cfg = MCPConfig()
    assert cfg.enabled is True
    assert cfg.connect_timeout == 10.0


def test_mcp_config_from_dict():
    cfg = MinagentConfig.from_dict({"mcp": {"enabled": False, "connect_timeout": 5.0}})
    assert cfg.mcp.enabled is False
    assert cfg.mcp.connect_timeout == 5.0
