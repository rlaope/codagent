"""``StateTracer`` — record per-node before/after state shape and timing."""

from __future__ import annotations

import json
import time
from typing import Any, Callable


class StateTracer:
    """Wraps node callables to record execution traces.

    Use ``wrap_node(node, name=...)`` to produce a recording version of
    your node. The tracer accumulates step records you can inspect via
    ``steps`` or export via ``to_json``.
    """

    def __init__(self, *, on_step: Callable[[dict], None] | None = None):
        self.on_step = on_step
        self.steps: list[dict] = []

    def trace_step(
        self,
        name: str,
        state_before: Any,
        state_after: Any,
        duration_seconds: float,
        error: str | None = None,
    ) -> None:
        rec = {
            "name": name,
            "duration_seconds": round(duration_seconds, 4),
            "before_keys": _state_keys(state_before),
            "after_keys": _state_keys(state_after),
            "timestamp": time.time(),
            "error": error,
        }
        self.steps.append(rec)
        if self.on_step is not None:
            self.on_step(rec)

    def wrap_node(self, node: Callable, *, name: str | None = None) -> Callable:
        node_name = name or getattr(node, "__name__", "anonymous")

        def wrapper(state):
            t0 = time.monotonic()
            try:
                result = node(state)
            except Exception as e:
                self.trace_step(
                    node_name, state, None, time.monotonic() - t0, error=type(e).__name__
                )
                raise
            self.trace_step(node_name, state, result, time.monotonic() - t0)
            return result

        wrapper.__wrapped__ = node  # type: ignore[attr-defined]
        return wrapper

    def to_json(self) -> str:
        return json.dumps(self.steps, indent=2, default=str)

    def __len__(self) -> int:
        return len(self.steps)


def _state_keys(state: Any) -> list[str] | None:
    if isinstance(state, dict):
        return list(state.keys())
    return None
