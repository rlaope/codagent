"""``with_loop_guard`` — kill agent tool thrashing.

Wraps a callable (typically a tool) and tracks recent invocation
fingerprints. When the same fingerprint repeats more than
``max_repeats`` times within the rolling window, raise ``LoopDetected``.

Catches the classic "agent calls search_orders('foo') 47 times" failure
mode that consumes tokens without producing progress. Mentioned in 90%
of agent loop root-cause analyses (Markaicode, Gemini CLI thread,
deer-flow#1055) but not built into LangGraph.
"""

from __future__ import annotations

import json
from collections import deque
from typing import Any, Callable, Hashable


class LoopDetected(Exception):
    """Raised when a callable is invoked with the same fingerprint too often."""


def _default_key(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    """JSON-serialize args/kwargs for a stable, hashable fingerprint.

    Falls back to ``repr`` for non-JSON-encodable values. Order of
    kwargs is normalized so call-site order does not affect equality.
    """
    try:
        return json.dumps(
            {"args": args, "kwargs": kwargs},
            sort_keys=True,
            default=repr,
        )
    except TypeError:
        return repr((args, tuple(sorted(kwargs.items()))))


def with_loop_guard(
    fn: Callable,
    *,
    window: int = 10,
    max_repeats: int = 3,
    key_fn: Callable[..., Hashable] | None = None,
) -> Callable:
    """Wrap a callable so repeated identical invocations raise.

    Args:
        fn: callable to guard (typically a tool function)
        window: how many recent calls to remember; older calls drop out
        max_repeats: how many identical fingerprints are allowed in the
            window before the next identical call raises. ``max_repeats=3``
            means the 4th identical call within the window raises.
        key_fn: custom fingerprint function ``(*args, **kwargs) -> hashable``;
            default JSON-serializes args/kwargs.

    Each guarded callable owns its own history deque, so wrapping the
    same underlying function twice gives independent counters. To share
    state across paths, wrap once and reuse the result.
    """
    if window < 1:
        raise ValueError("window must be >= 1")
    if max_repeats < 1:
        raise ValueError("max_repeats must be >= 1")

    history: deque[Hashable] = deque(maxlen=window)

    def wrapper(*args: Any, **kwargs: Any):
        key = key_fn(*args, **kwargs) if key_fn else _default_key(args, kwargs)
        existing = sum(1 for k in history if k == key)
        if existing >= max_repeats:
            raise LoopDetected(
                f"loop detected: same call fingerprint repeated "
                f"{existing + 1} times within window={window} "
                f"(max_repeats={max_repeats})"
            )
        history.append(key)
        return fn(*args, **kwargs)

    wrapper.__wrapped__ = fn  # type: ignore[attr-defined]
    wrapper._loop_guard_history = history  # type: ignore[attr-defined]
    return wrapper
