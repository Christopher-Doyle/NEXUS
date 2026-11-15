"""Small in-process safeguard for the single-owner loopback API."""

import math
import time
from collections import defaultdict, deque
from threading import Lock


class RateLimiter:
    def __init__(self, mutation_limit: int = 120, planning_limit: int = 20, window_seconds: int = 60) -> None:
        self.mutation_limit = mutation_limit
        self.planning_limit = planning_limit
        self.window_seconds = window_seconds
        self._calls: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def retry_after(self, client: str, bucket: str) -> int | None:
        now = time.monotonic()
        limit = self.planning_limit if bucket == "planning" else self.mutation_limit
        key = (client, bucket)
        with self._lock:
            calls = self._calls[key]
            while calls and calls[0] <= now - self.window_seconds:
                calls.popleft()
            if len(calls) >= limit:
                return max(1, math.ceil(self.window_seconds - (now - calls[0])))
            calls.append(now)
        return None
