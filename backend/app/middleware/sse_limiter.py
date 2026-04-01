"""SSE connection rate limiter — caps concurrent streams per email."""

import asyncio
from collections import defaultdict


class SSEConnectionTracker:
    MAX_CONNECTIONS_PER_EMAIL = 3

    def __init__(self) -> None:
        self._active: dict[str, int] = defaultdict(int)
        self._lock = asyncio.Lock()

    async def acquire(self, email: str) -> bool:
        """Increment connection count if under limit. Returns True on success."""
        async with self._lock:
            if self._active[email] >= self.MAX_CONNECTIONS_PER_EMAIL:
                return False
            self._active[email] += 1
            return True

    async def release(self, email: str) -> None:
        """Decrement connection count (floor at 0), clean up key if zero."""
        async with self._lock:
            self._active[email] = max(0, self._active[email] - 1)
            if self._active[email] == 0:
                del self._active[email]
