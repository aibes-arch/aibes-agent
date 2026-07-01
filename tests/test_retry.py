import pytest

from aibes_agent.core.retry import async_retry


@pytest.mark.asyncio
async def test_async_retry_success_first_try():
    async def coro():
        return "ok"

    result = await async_retry(coro, max_retries=0)
    assert result == "ok"


@pytest.mark.asyncio
async def test_async_retry_success_after_failures():
    calls = []

    async def coro():
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("fail")
        return "ok"

    result = await async_retry(coro, max_retries=3, delay=0.01)
    assert result == "ok"
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_async_retry_exhausted():
    async def coro():
        raise RuntimeError("always fail")

    with pytest.raises(RuntimeError, match="always fail"):
        await async_retry(coro, max_retries=2, delay=0.01)


@pytest.mark.asyncio
async def test_async_retry_only_catches_specified_exceptions():
    async def coro():
        raise ValueError("unexpected")

    with pytest.raises(ValueError, match="unexpected"):
        await async_retry(coro, max_retries=2, delay=0.01, retry_on=(RuntimeError,))
