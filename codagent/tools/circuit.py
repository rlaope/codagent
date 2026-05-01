"""``circuit_breaker`` — open after N consecutive failures.

Three-state breaker:
    CLOSED      normal call-through
    OPEN        fast-fail with CircuitBreakerOpen for `reset_after` seconds
    HALF_OPEN   one trial call after the cooldown; success closes, fail re-opens

Per-decorator state — each decorated callable has its own breaker.
"""

from __future__ import annotations

import time
from enum import Enum
from threading import Lock
from typing import Callable


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpen(Exception):
    """Raised by a fast-failing breaker."""


class _Breaker:
    def __init__(self, threshold: int, reset_after: float):
        self.threshold = threshold
        self.reset_after = reset_after
        self.failures = 0
        self.opened_at: float | None = None
        self.state: CircuitState = CircuitState.CLOSED
        self._lock = Lock()

    def call(self, fn, args, kwargs):
        with self._lock:
            if self.state is CircuitState.OPEN:
                assert self.opened_at is not None
                if time.monotonic() - self.opened_at >= self.reset_after:
                    self.state = CircuitState.HALF_OPEN
                else:
                    raise CircuitBreakerOpen(
                        f"breaker open for {self.reset_after - (time.monotonic() - self.opened_at):.1f}s more"
                    )

        try:
            result = fn(*args, **kwargs)
        except Exception:
            with self._lock:
                self.failures += 1
                if self.failures >= self.threshold:
                    self.state = CircuitState.OPEN
                    self.opened_at = time.monotonic()
            raise
        else:
            with self._lock:
                self.failures = 0
                self.state = CircuitState.CLOSED
                self.opened_at = None
            return result


def circuit_breaker(
    *,
    failure_threshold: int = 5,
    reset_after: float = 60.0,
) -> Callable[[Callable], Callable]:
    """Decorator factory: wrap a tool with a circuit breaker."""
    if failure_threshold < 1:
        raise ValueError("failure_threshold must be >= 1")
    if reset_after <= 0:
        raise ValueError("reset_after must be > 0")

    def decorator(fn: Callable) -> Callable:
        breaker = _Breaker(failure_threshold, reset_after)

        def wrapper(*args, **kwargs):
            return breaker.call(fn, args, kwargs)

        wrapper.__wrapped__ = fn  # type: ignore[attr-defined]
        wrapper.breaker = breaker  # type: ignore[attr-defined]
        return wrapper

    return decorator
