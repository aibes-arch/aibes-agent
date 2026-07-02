import httpx
import pytest

from aibes_agent.core.llm import LLMClient, LLMResponse


@pytest.fixture
def client():
    return LLMClient(base_url="http://test", api_key="test-key", model="test-model")


@pytest.mark.asyncio
async def test_llm_chat_success(client, httpx_mock):
    httpx_mock.add_response(
        url="http://test/chat/completions",
        json={
            "choices": [
                {
                    "message": {
                        "content": "Hello",
                        "role": "assistant",
                    }
                }
            ],
            "model": "test-model",
            "usage": {"prompt_tokens": 10, "completion_tokens": 2},
        },
    )

    result = await client.chat(messages=[{"role": "user", "content": "Hi"}])

    assert isinstance(result, LLMResponse)
    assert result.content == "Hello"
    assert result.model == "test-model"
    assert result.usage["completion_tokens"] == 2

    request = httpx_mock.get_request(url="http://test/chat/completions")
    body = request.content.decode("utf-8")
    assert "test-model" in body
    assert "test-key" in request.headers.get("authorization", "")


@pytest.mark.asyncio
async def test_llm_chat_with_tools(client, httpx_mock):
    httpx_mock.add_response(
        url="http://test/chat/completions",
        json={
            "choices": [
                {
                    "message": {
                        "content": "",
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {"name": "FileRead", "arguments": "{}"},
                            }
                        ],
                    }
                }
            ],
            "model": "test-model",
            "usage": {},
        },
    )

    result = await client.chat(
        messages=[{"role": "user", "content": "read file"}],
        tools=[{"type": "function", "function": {"name": "FileRead"}}],
    )

    assert result.has_tool_calls()
    assert result.tool_calls[0]["function"]["name"] == "FileRead"

    request = httpx_mock.get_request(url="http://test/chat/completions")
    body = request.content.decode("utf-8")
    assert "tool_choice" in body


@pytest.mark.httpx_mock(can_send_already_matched_responses=True)
@pytest.mark.asyncio
async def test_llm_chat_http_error(client, httpx_mock):
    httpx_mock.add_response(
        url="http://test/chat/completions",
        status_code=500,
        text="Server error",
    )

    with pytest.raises(httpx.HTTPStatusError):
        await client.chat(messages=[{"role": "user", "content": "Hi"}])


def test_llm_with_model():
    client = LLMClient(base_url="http://test", api_key="key", model="base")
    same = client.with_model("base")
    assert same is client

    different = client.with_model("other")
    assert different.model == "other"
    assert different.base_url == client.base_url


def test_llm_response_from_openai():
    data = {
        "choices": [{"message": {"content": "OK", "tool_calls": []}}],
        "model": "m",
        "usage": {"total_tokens": 5},
    }
    resp = LLMResponse.from_openai(data)
    assert resp.content == "OK"
    assert resp.model == "m"
    assert resp.usage["total_tokens"] == 5
