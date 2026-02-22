import time
from collections import defaultdict


class RateLimiter:
    """Simple in-memory sliding-window rate limiter."""

    def __init__(self, max_attempts: int = 5, window_seconds: int = 900):
        self._attempts: dict[str, list[float]] = defaultdict(list)
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds

    def is_limited(self, key: str) -> bool:
        now = time.time()
        self._attempts[key] = [
            t for t in self._attempts[key] if now - t < self.window_seconds
        ]
        return len(self._attempts[key]) >= self.max_attempts

    def record(self, key: str):
        self._attempts[key].append(time.time())


login_limiter = RateLimiter(max_attempts=5, window_seconds=900)
