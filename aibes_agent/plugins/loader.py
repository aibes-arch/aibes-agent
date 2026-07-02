"""Plugin discovery and loading.

Supports two discovery sources:

1. Local directories (default: ``.aibes-agent/plugins``) containing a
   ``plugin.yaml`` and/or ``__init__.py`` with an ``__aibes_plugin__`` dict.
2. Installed packages declaring ``aibes_agent.plugins`` entry points.
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import sys
import types
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

import yaml
from loguru import logger

from aibes_agent.plugins.plugin import Plugin
from aibes_agent.skills.skill import Skill
from aibes_agent.tools.agent import AgentProfile
from aibes_agent.tools.base import Tool


class PluginLoader:
    """Discover and load aibes-agent plugins from directories and entry points."""

    def __init__(
        self,
        search_paths: Optional[List[str]] = None,
        entry_point_group: str = "aibes_agent.plugins",
        load_entry_points: bool = True,
    ) -> None:
        self.search_paths: List[str] = search_paths or [".aibes-agent/plugins"]
        self.entry_point_group: str = entry_point_group
        self.load_entry_points: bool = load_entry_points

    def load_all(self) -> List[Plugin]:
        """Load all plugins from entry points and configured paths."""
        plugins: List[Plugin] = []
        seen: Dict[str, Plugin] = {}

        if self.load_entry_points:
            for plugin in self._load_entry_points():
                if plugin.name in seen:
                    logger.warning(
                        "Duplicate plugin name '{}' from {} and {}; using the first one",
                        plugin.name,
                        seen[plugin.name].source,
                        plugin.source,
                    )
                    continue
                seen[plugin.name] = plugin
                plugins.append(plugin)

        for raw_path in self.search_paths:
            path = Path(raw_path).expanduser().resolve()
            if not path.exists():
                continue

            if path.is_file() and path.name == "plugin.yaml":
                loaded_plugin = self._load_directory(path.parent)
                if loaded_plugin is not None:
                    self._add_plugin(loaded_plugin, seen, plugins)
                continue

            if not path.is_dir():
                continue

            for subdir in sorted(path.iterdir()):
                if not subdir.is_dir():
                    continue
                if subdir.name.startswith(".") or subdir.name == "__pycache__":
                    continue
                loaded_plugin = self._load_directory(subdir)
                if loaded_plugin is not None:
                    self._add_plugin(loaded_plugin, seen, plugins)

        return plugins

    def _add_plugin(self, plugin: Plugin, seen: Dict[str, Plugin], plugins: List[Plugin]) -> None:
        if plugin.name in seen:
            logger.warning(
                "Duplicate plugin name '{}' from {} and {}; using the first one",
                plugin.name,
                seen[plugin.name].source,
                plugin.source,
            )
            return
        seen[plugin.name] = plugin
        plugins.append(plugin)

    def _load_entry_points(self) -> List[Plugin]:
        """Load plugins declared via ``importlib.metadata`` entry points."""
        plugins: List[Plugin] = []
        try:
            eps = importlib.metadata.entry_points(group=self.entry_point_group)
        except Exception as exc:
            logger.warning(
                "Failed to read entry points for group '{}': {}", self.entry_point_group, exc
            )
            return plugins

        for ep in eps:
            try:
                module = ep.load()
                if not isinstance(module, types.ModuleType):
                    module = importlib.import_module(str(ep.value))
            except Exception as exc:
                logger.warning("Failed to load plugin entry point '{}': {}", ep.name, exc)
                continue

            plugin = self._load_module(module, source=f"entry_point:{ep.name}")
            if plugin is not None:
                plugins.append(plugin)

        return plugins

    def _load_directory(self, directory: Path) -> Optional[Plugin]:
        """Load a single plugin directory."""
        plugin_file = directory / "plugin.yaml"
        init_file = directory / "__init__.py"

        # Skip directories that do not look like plugin packages.
        if not plugin_file.exists() and not init_file.exists():
            return None

        data: Dict[str, Any] = {}
        if plugin_file.exists():
            try:
                with plugin_file.open("r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
            except Exception as exc:
                logger.warning("Failed to read {}: {}", plugin_file, exc)
                return None

        module_name = data.get("module", directory.name)
        module = self._import_plugin_module(directory, module_name, plugin_file.exists())
        if module is None:
            return None

        plugin = self._load_module(module, source=f"path:{directory}")
        if plugin is None:
            return None

        # plugin.yaml values can override module-level metadata.
        if "name" in data:
            plugin.name = str(data["name"])
        if "version" in data:
            plugin.version = str(data["version"])
        return plugin

    def _import_plugin_module(
        self, directory: Path, module_name: str, has_plugin_file: bool
    ) -> Optional[types.ModuleType]:
        """Import the plugin module from a directory, tolerating missing deps."""
        init_file = directory / "__init__.py"

        # Package-style plugin: directory contains __init__.py.
        if init_file.exists():
            parent = directory.parent
            with self._sys_path_inserted(parent):
                try:
                    return importlib.import_module(module_name)
                except Exception as exc:
                    logger.warning("Failed to import plugin package '{}': {}", module_name, exc)
                    return None

        # Module-style plugin: a single .py file.
        module_file = directory / f"{module_name}.py"
        if not module_file.exists():
            # Fallback to a conventional plugin.py.
            module_file = directory / "plugin.py"
            if module_file.exists():
                module_name = module_file.stem

        if module_file.exists():
            with self._sys_path_inserted(directory):
                try:
                    spec = importlib.util.spec_from_file_location(module_name, module_file)
                    if spec is None or spec.loader is None:
                        logger.warning("Cannot create module spec for '{}'", module_file)
                        return None
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)
                    return module
                except Exception as exc:
                    logger.warning("Failed to load plugin module '{}': {}", module_file, exc)
                    # Clean up partial module registration.
                    sys.modules.pop(module_name, None)
                    return None

        if has_plugin_file:
            logger.warning("No plugin module found in '{}'", directory)
        return None

    def _load_module(self, module: types.ModuleType, source: str = "") -> Optional[Plugin]:
        """Create a Plugin from a module using ``__aibes_plugin__`` or ``setup``."""
        plugin_dict: Optional[Dict[str, Any]] = getattr(module, "__aibes_plugin__", None)
        setup_callback = getattr(module, "setup", None)

        if plugin_dict is None and not callable(setup_callback):
            logger.warning(
                "Module '{}' has neither __aibes_plugin__ nor setup(); skipping",
                getattr(module, "__name__", source),
            )
            return None

        name = ""
        version = "0.0.0"
        tools: List[Tool] = []
        skills: List[Skill] = []
        profiles: Dict[str, AgentProfile] = {}

        if isinstance(plugin_dict, dict):
            name = str(plugin_dict.get("name", getattr(module, "__name__", "")))
            version = str(plugin_dict.get("version", getattr(module, "__version__", "0.0.0")))

            for item in plugin_dict.get("tools", []):
                tool = self._coerce_tool(item, source)
                if tool is not None:
                    tools.append(tool)

            for item in plugin_dict.get("skills", []):
                if isinstance(item, Skill):
                    skills.append(item)
                else:
                    logger.warning("Plugin {} skill item is not a Skill instance: {}", source, item)

            for key, value in plugin_dict.get("profiles", {}).items():
                if isinstance(value, AgentProfile):
                    profiles[str(key)] = value
                else:
                    logger.warning(
                        "Plugin {} profile '{}' is not an AgentProfile instance: {}",
                        source,
                        key,
                        value,
                    )
        else:
            name = getattr(module, "__name__", "")
            version = getattr(module, "__version__", "0.0.0")

        if not name:
            name = source.rsplit(":", 1)[-1] if source else "unknown"

        return Plugin(
            name=name,
            version=version,
            module=module,
            tools=tools,
            skills=skills,
            profiles=profiles,
            setup=setup_callback if callable(setup_callback) else None,
            source=source,
        )

    @staticmethod
    def _coerce_tool(item: Any, source: str) -> Optional[Tool]:
        """Convert a Tool subclass or instance into a Tool instance."""
        try:
            if isinstance(item, type) and issubclass(item, Tool):
                return item()
            if isinstance(item, Tool):
                return item
        except Exception as exc:
            logger.warning("Failed to instantiate tool from plugin {}: {}", source, exc)
            return None
        logger.warning("Plugin {} tool item is not a Tool subclass/instance: {}", source, item)
        return None

    @staticmethod
    @contextmanager
    def _sys_path_inserted(path: Path) -> Generator[None, None, None]:
        """Context manager that temporarily inserts *path* into ``sys.path``."""
        path_str = str(path)
        added = path_str not in sys.path
        if added:
            sys.path.insert(0, path_str)
        try:
            yield
        finally:
            if added:
                try:
                    sys.path.remove(path_str)
                except ValueError:
                    pass
