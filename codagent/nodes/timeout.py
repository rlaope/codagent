"""``with_timeout`` — bound a node's wall-clock execution.

Uses ``concurrent.futures.ThreadPoolExecutor`` so the timeout works
cross-platform and inside any thread (signal-based timeouts are
limited to the main thread on Unix).

The wrapped callable raises ``NodeTimeout`` when the inner call exceeds
the limit. Note that the inner thread is not forcibly killed — Python
cannot safely kill threads — so a timed-out node continues to run in
the background until it completes naturally.
"""

from __future__ import annotations

import concurrent.futures
from typing import Callable


class NodeTimeout(TimeoutError):
    """Raised when a node wrapped with ``with_timeout`` exceeds its budget."""


def with_timeout(node: Callable, *, seconds: float) -> Callable:
    if seconds <= 0:
        raise ValueError("seconds must be > 0")

    def wrapper(state):
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(node, state)
            try:
                return future.result(timeout=seconds)
            except concurrent.futures.TimeoutError:
                raise NodeTimeout(
                    f"node exceeded {seconds}s timeout"
                ) from None

    wrapper.__wrapped__ = node  # type: ignore[attr-defined]
    return wrapper
