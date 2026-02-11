import asyncio
import time


class RateLimiter:
    def __init__(self, max_rps: int):
        self._min_delay_ms = max(1, 1000 // max_rps) if max_rps > 0 else 0
        self._next_time = 0

    async def wait(self) -> None:
        if self._min_delay_ms == 0:
            return
        now = int(time.time() * 1000)
        scheduled = max(now, self._next_time)
        self._next_time = scheduled + self._min_delay_ms
        delay = scheduled - now
        if delay > 0:
            await asyncio.sleep(delay / 1000)


def create_rate_limiter(max_rps: int) -> RateLimiter | None:
    if max_rps <= 0:
        return None
    return RateLimiter(max_rps)
