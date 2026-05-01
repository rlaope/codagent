"""``with_retry`` — retry a node on listed exception types.

Fixes the gap from langgraph#6027 (retry_policy silently dropping
ValidationError) by giving you full control over which exceptions
trigger a retry and using a transparent backoff schedule.
"""

from __future__ import annotations

import time
from typing import Callable


def with_retry(
    node: Callable,
    *,
    attempts: int = 3,
    backoff: float = 1.0,
    backoff_factor: float = 2.0,
    on: tuple[type[BaseException], ...] = (Exception,),
) -> Callable:
    """Wrap a node so transient failures retry with exponential backoff.

    Args:
        node: callable to wrap (state -> state-update)
        attempts: total attempts including the first try (>= 1)
        backoff: initial sleep seconds before second attempt
        backoff_factor: multiplier between attempts (2.0 = exponential)
        on: tuple of exception types that trigger a retry

    Raises the last seen exception if all attempts fail.
    """
    if attempts < 1:
        raise ValueError("attempts must be >= 1")

    def wrapper(state):
        last_err: BaseException | None = None
        for i in range(attempts):
            try:
                return node(state)
            except on as e:
                last_err = e
                if i < attempts - 1:
                    time.sleep(backoff * (backoff_factor ** i))
        assert last_err is not None
        raise last_err

    wrapper.__wrapped__ = node  # type: ignore[attr-defined]
    return wrapper
