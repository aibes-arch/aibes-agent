"""Demonstrate the greeting plugin both standalone and inside aibes-agent."""

from __future__ import annotations

import asyncio
import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# Add the parent of this plugin directory so ``greeting_plugin`` can be
# imported as a package.
PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_PARENT = os.path.dirname(PLUGIN_DIR)
if PLUGIN_PARENT not in sys.path:
    sys.path.insert(0, PLUGIN_PARENT)

from aibes_agent import PluginLoader, ToolContext
from aibes_agent.core.tool_registry import ToolRegistry

# Standalone usage: the greeting module does not depend on aibes-agent.
from greeting_plugin import greet, list_styles


def demo_standalone() -> None:
    print("=== Standalone usage ===")
    print(f"Styles: {list_styles()}")
    for style in list_styles():
        print(f"  {style}: {greet('Alice', style)}")
    print()


async def demo_in_agent() -> None:
    print("=== Plugin usage via ToolRegistry ===")
    plugins = PluginLoader(search_paths=[PLUGIN_PARENT], load_entry_points=False).load_all()
    print(f"Loaded plugins: {[p.name for p in plugins]}")

    registry = ToolRegistry()
    for plugin in plugins:
        for tool in plugin.tools:
            registry.register(tool)

    ctx = ToolContext(cwd=os.getcwd())
    results = await registry.execute(
        [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "Greeting", "arguments": {"name": "Bob", "style": "casual"}},
            },
            {
                "id": "call_2",
                "type": "function",
                "function": {"name": "ListGreetingStyles", "arguments": {}},
            },
        ],
        ctx,
    )
    for result in results:
        print(f"[{result['name']}] {result['content']}")


async def main() -> None:
    demo_standalone()
    await demo_in_agent()


if __name__ == "__main__":
    asyncio.run(main())
