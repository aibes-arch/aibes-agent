"""Plugin extension system for aibes-agent."""

from __future__ import annotations

from aibes_agent.plugins.builder import PluginBuilder
from aibes_agent.plugins.loader import PluginLoader
from aibes_agent.plugins.plugin import Plugin

__all__ = ["Plugin", "PluginBuilder", "PluginLoader"]
