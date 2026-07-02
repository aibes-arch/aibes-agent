"""Greeting plugin for aibes-agent.

The plugin exposes two tools: ``Greeting`` and ``ListGreetingStyles``.
The underlying ``greeting`` module can be used independently of the framework.
"""

from __future__ import annotations

from .greeting import greet, list_styles
from .tool import GreetingTool, ListGreetingStylesTool

__version__ = "1.0.0"

__all__ = ["greet", "list_styles", "GreetingTool", "ListGreetingStylesTool"]

__aibes_plugin__ = {
    "name": "greeting",
    "version": __version__,
    "tools": [GreetingTool, ListGreetingStylesTool],
}
