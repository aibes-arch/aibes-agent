"""Session summarization utilities."""

from __future__ import annotations

from typing import Optional

from aibes_agent.core.llm import LLMClient
from aibes_agent.core.session import SessionState


class SessionSummarizer:
    """Summarize a session state into a short text using an LLM."""

    def __init__(self, llm: LLMClient, max_messages: int = 100) -> None:
        self.llm = llm
        self.max_messages = max_messages

    async def summarize(self, state: SessionState) -> str:
        """Return a concise summary of *state*."""
        messages = state.messages[: self.max_messages]
        transcript = "\n".join(
            f"{m.get('role', 'unknown')}: {m.get('content', '') or ''}" for m in messages
        )
        if not transcript.strip():
            return ""

        prompt = (
            "Summarize the following agent conversation in 2-3 sentences. "
            "Focus on the user's goal, key actions taken, and any important results.\n\n"
            f"{transcript}\n\nSummary:"
        )

        try:
            response = await self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=256,
                temperature=0.2,
            )
            return response.content.strip()
        except Exception:
            return ""
