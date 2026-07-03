"""Tests for session summarizer."""

from __future__ import annotations

import pytest

from aibes_agent.core.llm import LLMClient
from aibes_agent.core.session import SessionState
from aibes_agent.core.summarizer import SessionSummarizer


@pytest.fixture
def client():
    return LLMClient(base_url="http://test", api_key="key", model="test-model", max_retries=0)


@pytest.mark.asyncio
async def test_summarize_session(client, httpx_mock):
    state = SessionState(
        session_id="s1",
        messages=[
            {"role": "user", "content": "What is the weather?"},
            {"role": "assistant", "content": "It is sunny."},
        ],
    )
    httpx_mock.add_response(
        url="http://test/chat/completions",
        json={
            "choices": [{"message": {"content": "User asked about weather; assistant said sunny."}}]
        },
    )
    summarizer = SessionSummarizer(llm=client)
    summary = await summarizer.summarize(state)
    assert "weather" in summary.lower()


@pytest.mark.asyncio
async def test_summarize_empty_session(client):
    state = SessionState(session_id="s1", messages=[])
    summarizer = SessionSummarizer(llm=client)
    assert await summarizer.summarize(state) == ""


@pytest.mark.asyncio
async def test_summarize_llm_error(client, httpx_mock):
    state = SessionState(
        session_id="s1",
        messages=[{"role": "user", "content": "Hi"}],
    )
    httpx_mock.add_response(url="http://test/chat/completions", status_code=500)
    summarizer = SessionSummarizer(llm=client)
    assert await summarizer.summarize(state) == ""
