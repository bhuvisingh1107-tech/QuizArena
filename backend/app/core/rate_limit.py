"""Simple in-memory rate limiter for login (NFR-023)."""

import time
from collections import defaultdict
from threading import Lock

from app.core.exceptions import QuizArenaError


class RateLimitError(QuizArenaError):
    """Too many requests."""

    def __init__(self, message: str = "Too many login attempts. Please try again later.") -> None:
        super().__init__("RATE_LIMITED", message, status_code=429)


class InMemoryRateLimiter:
    """Fixed-window counter keyed by client identity (e.g. IP)."""

    def __init__(self, *, max_attempts: int = 10, window_seconds: int = 60) -> None:
        self._max_attempts = max_attempts
        self._window_seconds = window_seconds
        self._attempts: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        cutoff = now - self._window_seconds
        with self._lock:
            timestamps = [ts for ts in self._attempts[key] if ts >= cutoff]
            if len(timestamps) >= self._max_attempts:
                self._attempts[key] = timestamps
                raise RateLimitError()
            timestamps.append(now)
            self._attempts[key] = timestamps

    def reset(self) -> None:
        """Clear all tracked attempts (used by tests)."""
        with self._lock:
            self._attempts.clear()


login_rate_limiter = InMemoryRateLimiter(max_attempts=10, window_seconds=60)
join_rate_limiter = InMemoryRateLimiter(max_attempts=30, window_seconds=60)
