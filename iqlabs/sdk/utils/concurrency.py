import asyncio
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


async def run_with_concurrency(
    items: list[T],
    limit: int,
    worker: Callable[[T, int], Awaitable[None]],
) -> None:
    if not items:
        return
    concurrency = max(1, min(limit, len(items)))
    cursor = 0
    lock = asyncio.Lock()

    async def runner():
        nonlocal cursor
        while True:
            async with lock:
                index = cursor
                cursor += 1
            if index >= len(items):
                return
            await worker(items[index], index)

    await asyncio.gather(*[runner() for _ in range(concurrency)])
