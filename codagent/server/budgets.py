"""Per-user budget gates for codagent.server.

A :class:`BudgetGate` enforces token / cost / step ceilings keyed by an
``identify(request) -> user_id`` hook. State is kept per user across
runs in the app's lifetime, so a user who blew their budget in run N
is rejected immediately on run N+1.

When a run causes the gate to exceed any limit, the runner emits a
``run.budget_exceeded`` event with the failing limit's name, the
current value, and the configured ceiling. The run terminates without
emitting ``run.done``.
"""

from __future__ import annotations

from dataclasses import dataclass

from codagent.observability.cost import MODEL_PRICES


@dataclass
class BudgetConfig:
    """Per-user limits. Any field set to ``None`` is unenforced."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    max_usd: float | None = None
    max_steps: int | None = None
    model: str | None = None  # used for USD computation


class BudgetGate:
    """Per-user-id budget enforcement.

    Build once per app and share across runs. Internally tracks
    ``input_tokens``, ``output_tokens``, ``usd``, and ``steps`` per
    user. :meth:`check` returns a violation dict or ``None``;
    :meth:`record_token` accumulates after a token is emitted.
    """

    def __init__(self, config: BudgetConfig) -> None:
        self.config = config
        self._state: dict[str, dict] = {}

    def _state_for(self, user_id: str) -> dict:
        return self._state.setdefault(
            user_id,
            {"input_tokens": 0, "output_tokens": 0, "usd": 0.0, "steps": 0},
        )

    def check(self, user_id: str) -> dict | None:
        s = self._state_for(user_id)
        c = self.config
        if c.input_tokens is not None and s["input_tokens"] >= c.input_tokens:
            return {"limit": "input_tokens", "value": s["input_tokens"], "ceiling": c.input_tokens}
        if c.output_tokens is not None and s["output_tokens"] >= c.output_tokens:
            return {"limit": "output_tokens", "value": s["output_tokens"], "ceiling": c.output_tokens}
        if c.max_usd is not None and s["usd"] >= c.max_usd:
            return {"limit": "usd", "value": s["usd"], "ceiling": c.max_usd}
        if c.max_steps is not None and s["steps"] >= c.max_steps:
            return {"limit": "steps", "value": s["steps"], "ceiling": c.max_steps}
        return None

    def record_token(self, user_id: str, kind: str = "output", count: int = 1) -> None:
        s = self._state_for(user_id)
        if kind == "output":
            s["output_tokens"] += count
        elif kind == "input":
            s["input_tokens"] += count
        s["steps"] += count
        model = self.config.model
        if model and model in MODEL_PRICES:
            in_price, out_price = MODEL_PRICES[model]
            if kind == "output":
                s["usd"] += (count / 1000) * out_price
            elif kind == "input":
                s["usd"] += (count / 1000) * in_price

    def state_of(self, user_id: str) -> dict:
        """Snapshot a user's accumulated usage. Convenience for tests."""
        return dict(self._state_for(user_id))
