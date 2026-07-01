"""异步重试工具。"""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Optional, Tuple, Type, TypeVar

T = TypeVar("T")


async def async_retry(
    coro_fn: Callable[[], Awaitable[T]],
    max_retries: int = 2,
    delay: float = 1.0,
    backoff: float = 2.0,
    retry_on: Tuple[Type[Exception], ...] = (Exception,),
) -> T:
    """执行一个异步函数，失败时按指数退避重试。

    Args:
        coro_fn: 需要执行的异步函数（无参数）。
        max_retries: 最大重试次数，总执行次数 = max_retries + 1。
        delay: 首次重试等待秒数。
        backoff: 退避系数。
        retry_on: 需要重试的异常类型元组。

    Returns:
        函数返回值。

    Raises:
        最后一次捕获的异常。
    """
    last_exc: Optional[Exception] = None
    current_delay = delay

    for attempt in range(max_retries + 1):
        try:
            return await coro_fn()
        except retry_on as exc:
            last_exc = exc
            if attempt >= max_retries:
                break
            await asyncio.sleep(current_delay)
            current_delay *= backoff

    assert last_exc is not None
    raise last_exc
