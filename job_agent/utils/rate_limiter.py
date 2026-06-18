"""Token-bucket rate limiter for pacing platform requests."""

from __future__ import annotations

import asyncio
import logging
import time

logger = logging.getLogger("job_agent.utils.rate_limiter")


class RateLimiter:
    """Async-safe token-bucket rate limiter.

    Ensures no more than `requests_per_minute` requests are made.
    """

    def __init__(self, requests_per_minute: int):
        self.rpm = requests_per_minute
        self.interval = 60.0 / requests_per_minute
        self._last_request_time: float = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until the next request is allowed under the rate limit."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            if elapsed < self.interval:
                wait_time = self.interval - elapsed
                logger.debug("Rate limiter: waiting %.1fs", wait_time)
                await asyncio.sleep(wait_time)
            self._last_request_time = time.monotonic()
