"""Project-level configuration loader for aibes_agent.

Supports ``aibes-agent.yaml`` and ``.aibes-agent/config.yaml`` with environment
variable overrides.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import yaml

from aibes_agent.core.cache import MemoryToolResultCache, SqliteToolResultCache, ToolResultCache
from aibes_agent.core.llm import LLMClient
from aibes_agent.core.session import (
    FileSessionStore,
    MemorySessionStore,
    RedisSessionStore,
    SessionStore,
    SQLiteSessionStore,
)

if TYPE_CHECKING:
    from aibes_agent.permissions.engine import PermissionEngine


@dataclass
class LLMConfig:
    """LLM connection settings."""

    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    timeout: float = 120.0
    max_retries: int = 2
    retry_delay: float = 1.0

    def to_llm_client(self) -> LLMClient:
        return LLMClient(
            base_url=self.base_url,
            api_key=self.api_key,
            model=self.model,
            timeout=self.timeout,
            max_retries=self.max_retries,
            retry_delay=self.retry_delay,
        )


@dataclass
class RouterRule:
    """Map a regex pattern on the task/prompt to a model name."""

    pattern: str
    model: str


@dataclass
class RouterConfig:
    """Simple regex-based model router."""

    default: Optional[str] = None
    rules: List[RouterRule] = field(default_factory=list)


@dataclass
class PermissionsConfig:
    """Permission engine settings."""

    mode: str = "auto"
    rules: List[Dict[str, str]] = field(default_factory=list)

    def to_permission_engine(self) -> "PermissionEngine":
        from aibes_agent.permissions.engine import PermissionEngine

        return PermissionEngine.from_config({"mode": self.mode, "rules": self.rules})


@dataclass
class SkillsConfig:
    """Skill discovery settings."""

    auto_load: bool = True
    paths: List[str] = field(default_factory=lambda: [".aibes-agent/skills"])


@dataclass
class PluginsConfig:
    """Plugin discovery settings."""

    auto_load: bool = True
    entry_points: bool = True
    paths: List[str] = field(default_factory=lambda: [".aibes-agent/plugins"])


@dataclass
class MCPServerConfig:
    """A single MCP server connection descriptor."""

    transport: str = "stdio"  # stdio or sse
    command: Optional[str] = None
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    url: Optional[str] = None


@dataclass
class SessionConfig:
    """Session persistence settings."""

    store: str = "file"
    path: str = ".aibes-agent/sessions"
    url: Optional[str] = None
    ttl: float = 0.0

    def to_session_store(self) -> SessionStore:
        store = self.store.lower()
        if store == "file":
            return FileSessionStore(self.path)
        if store == "memory":
            return MemorySessionStore()
        if store == "sqlite":
            return SQLiteSessionStore(self.path)
        if store == "redis":
            return RedisSessionStore(url=self.url or "redis://localhost:6379/0", ttl=self.ttl)
        raise ValueError(f"Unsupported session store: {self.store}")


@dataclass
class CacheConfig:
    """Tool result cache settings."""

    store: str = "memory"
    path: str = ".aibes-agent/cache.db"
    url: str = ""
    default_ttl: float = 60.0
    max_size: int = 10000

    def to_tool_result_cache(self) -> ToolResultCache:
        store = self.store.lower()
        if store == "memory":
            return MemoryToolResultCache(default_ttl=self.default_ttl)
        if store == "sqlite":
            return SqliteToolResultCache(
                path=self.path,
                default_ttl=self.default_ttl,
                max_size=self.max_size,
            )
        raise ValueError(f"Unsupported cache store: {self.store}")


@dataclass
class WebConfig:
    """Web UI server settings."""

    host: str = "127.0.0.1"
    port: int = 8000


@dataclass
class MinagentConfig:
    """Top-level aibes-agent configuration."""

    llm: LLMConfig = field(default_factory=LLMConfig)
    router: RouterConfig = field(default_factory=RouterConfig)
    permissions: PermissionsConfig = field(default_factory=PermissionsConfig)
    skills: SkillsConfig = field(default_factory=SkillsConfig)
    plugins: PluginsConfig = field(default_factory=PluginsConfig)
    mcp_servers: Dict[str, MCPServerConfig] = field(default_factory=dict)
    session: SessionConfig = field(default_factory=SessionConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    web: WebConfig = field(default_factory=WebConfig)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MinagentConfig":
        data = data or {}

        llm_data = data.get("llm", {})
        llm = LLMConfig(
            base_url=llm_data.get("base_url"),
            api_key=llm_data.get("api_key"),
            model=llm_data.get("model"),
            timeout=float(llm_data.get("timeout", 120.0)),
            max_retries=int(llm_data.get("max_retries", 2)),
            retry_delay=float(llm_data.get("retry_delay", 1.0)),
        )

        router_data = data.get("router", {})
        router_rules = [
            RouterRule(pattern=r.get("pattern", ""), model=r.get("model", ""))
            for r in router_data.get("rules", [])
        ]
        router = RouterConfig(
            default=router_data.get("default"),
            rules=router_rules,
        )

        perm_data = data.get("permissions", {})
        permissions = PermissionsConfig(
            mode=perm_data.get("mode", "auto"),
            rules=[
                {
                    "action": r.get("action", ""),
                    "resource_type": r.get("resource_type", ""),
                    "pattern": r.get("pattern", ""),
                }
                for r in perm_data.get("rules", [])
            ],
        )

        skills_data = data.get("skills", {})
        skills = SkillsConfig(
            auto_load=bool(skills_data.get("auto_load", True)),
            paths=list(skills_data.get("paths", [".aibes-agent/skills"])),
        )

        plugins_data = data.get("plugins", {})
        plugins = PluginsConfig(
            auto_load=bool(plugins_data.get("auto_load", True)),
            entry_points=bool(plugins_data.get("entry_points", True)),
            paths=list(plugins_data.get("paths", [".aibes-agent/plugins"])),
        )

        mcp_servers: Dict[str, MCPServerConfig] = {}
        for name, srv in data.get("mcp_servers", {}).items():
            mcp_servers[name] = MCPServerConfig(
                transport=srv.get("transport", "stdio"),
                command=srv.get("command"),
                args=list(srv.get("args", [])),
                env=dict(srv.get("env", {})),
                url=srv.get("url"),
            )

        session_data = data.get("session", {})
        session = SessionConfig(
            store=session_data.get("store", "file"),
            path=session_data.get("path", ".aibes-agent/sessions"),
            url=session_data.get("url"),
            ttl=float(session_data.get("ttl", 0.0)),
        )

        cache_data = data.get("cache", {})
        cache = CacheConfig(
            store=cache_data.get("store", "memory"),
            path=cache_data.get("path", ".aibes-agent/cache.db"),
            url=cache_data.get("url", ""),
            default_ttl=float(cache_data.get("default_ttl", 60.0)),
            max_size=int(cache_data.get("max_size", 10000)),
        )

        web_data = data.get("web", {})
        web = WebConfig(
            host=web_data.get("host", "127.0.0.1"),
            port=int(web_data.get("port", 8000)),
        )

        cfg = cls(
            llm=llm,
            router=router,
            permissions=permissions,
            skills=skills,
            plugins=plugins,
            mcp_servers=mcp_servers,
            session=session,
            cache=cache,
            web=web,
        )
        cfg._apply_env_overrides()
        return cfg

    @classmethod
    def load(cls, path: Optional[str] = None) -> "MinagentConfig":
        """Load configuration from YAML.

        Search order:
        1. Explicit ``path`` argument
        2. ``AIBES_AGENT_CONFIG`` environment variable
        3. ``./aibes-agent.yaml``
        4. ``./.aibes-agent/config.yaml``
        """
        if path:
            config_path = Path(path).expanduser().resolve()
            if not config_path.exists():
                raise FileNotFoundError(f"Config file not found: {path}")
            return cls._from_path(config_path)

        env_path = os.getenv("AIBES_AGENT_CONFIG")
        if env_path:
            config_path = Path(env_path).expanduser().resolve()
            if config_path.exists():
                return cls._from_path(config_path)

        candidates = [Path("aibes-agent.yaml"), Path(".aibes-agent") / "config.yaml"]
        for candidate in candidates:
            candidate = candidate.expanduser().resolve()
            if candidate.exists():
                return cls._from_path(candidate)

        return cls()

    @classmethod
    def _from_path(cls, path: Path) -> "MinagentConfig":
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data)

    def _apply_env_overrides(self) -> None:
        """Allow a handful of environment variables to override YAML."""
        if os.getenv("AIBES_AGENT_BASE_URL"):
            self.llm.base_url = os.environ["AIBES_AGENT_BASE_URL"]
        if os.getenv("AIBES_AGENT_API_KEY"):
            self.llm.api_key = os.environ["AIBES_AGENT_API_KEY"]
        if os.getenv("AIBES_AGENT_MODEL"):
            self.llm.model = os.environ["AIBES_AGENT_MODEL"]

    def to_llm_client(self) -> LLMClient:
        return self.llm.to_llm_client()

    def to_permission_engine(self) -> "PermissionEngine":
        return self.permissions.to_permission_engine()

    def to_session_store(self) -> SessionStore:
        return self.session.to_session_store()

    def to_tool_result_cache(self) -> ToolResultCache:
        return self.cache.to_tool_result_cache()
