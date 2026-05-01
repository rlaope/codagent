"""``rate_limit`` — sliding-window rate limiter.

Default behavior is to **raise** ``RateLimitExceeded`` when the limit is
hit. Pass ``raise_on_exceed=False`` to instead block (sleep) until the
oldest call falls out of the window.
"""

from __future__ import annotations

import time
from collections import deque
from threading import Lock
from typing import Callable


class RateLimitExceeded(Exception):
    """Raised when the configured rate is exceeded (and raise_on_exceed=True)."""


def rate_limit(
    *,
    per_second: float,
    raise_on_exceed: bool = True,
) -> Callable[[Callable], Callable]:
    """Decorator factory: limit calls per 1-second sliding window."""
    if per_second <= 0:
        raise ValueError("per_second must be > 0")

    def decorator(fn: Callable) -> Callable:
        calls: deque[float] = deque()
        lock = Lock()
        window = 1.0
        capacity = per_second

        def wrapper(*args, **kwargs):
            while True:
                with lock:
                    now = time.monotonic()
                    while calls and calls[0] < now - window:
                        calls.popleft()
                    if len(calls) < capacity:
                        calls.append(now)
                        break
                    if raise_on_exceed:
                        raise RateLimitExceeded(
                            f"rate limit {per_second}/s exceeded"
                        )
                    sleep_for = window - (now - calls[0])
                # Outside the lock, sleep then re-loop.
                time.sleep(max(sleep_for, 0.001))
            return fn(*args, **kwargs)

        wrapper.__wrapped__ = fn  # type: ignore[attr-defined]
        return wrapper

    return decorator
