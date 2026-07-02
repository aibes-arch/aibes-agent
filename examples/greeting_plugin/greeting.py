"""Pure business logic for the greeting plugin.

This module has no dependency on aibes-agent and can be imported and used
independently.
"""

from __future__ import annotations

STYLES = {
    "formal": "Hello, {name}. Welcome!",
    "casual": "Hey {name}!",
    "excited": "Hello, {name}! Great to see you!",
}


def greet(name: str, style: str = "formal") -> str:
    """Return a greeting message for *name* using *style*."""
    template = STYLES.get(style, STYLES["formal"])
    return template.format(name=name)


def list_styles() -> list[str]:
    """Return available greeting styles."""
    return list(STYLES.keys())


if __name__ == "__main__":
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "World"
    for s in list_styles():
        print(f"[{s}] {greet(target, s)}")
