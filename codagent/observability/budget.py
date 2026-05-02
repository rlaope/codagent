"""``BudgetCap`` — hard USD ceiling on top of a CostTracker.

CostTracker measures spend passively. BudgetCap raises ``BudgetExceeded``
once a configured USD threshold is crossed, so a runaway retry loop or
tool-thrash agent dies fast instead of burning $200 in 20 minutes.

Pattern is the standard "agent kill-switch" guardrail recommended in
production playbooks (Markaicode, Last9, Praxen) — LangGraph leaves it
to the developer.
"""

from __future__ import annotations

from dataclasses import dataclass

from codagent.observability.cost import CostTracker
from codagent.observability.steps import BudgetExceeded


@dataclass
class BudgetCap:
    """Wrap a ``CostTracker`` with a hard USD limit.

    Two usage modes:

    1. Manual checkpoint: call ``cap.check()`` at safe points
       (e.g. after each graph step, before launching new tool calls).
    2. Auto on every LLM call: route ``record_call`` through the cap,
       which delegates to the tracker and immediately re-checks.

    ``BudgetCap`` does not modify ``CostTracker`` — multiple caps can
    observe the same tracker.
    """

    tracker: CostTracker
    usd: float

    def __post_init__(self) -> None:
        if self.usd <= 0:
            raise ValueError("usd cap must be > 0")

    def record_call(
        self,
        *,
        input_tokens: int = 0,
        output_tokens: int = 0,
        model: str | None = None,
    ) -> None:
        """Record on the tracker, then raise if cap is now breached."""
        self.tracker.record_call(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=model,
        )
        self.check()

    def check(self) -> None:
        """Raise ``BudgetExceeded`` if cumulative USD has crossed the cap."""
        spent = self.tracker.total_usd
        if spent >= self.usd:
            raise BudgetExceeded(
                f"USD budget cap ${self.usd:.4f} exceeded "
                f"(spent ${spent:.4f}, model={self.tracker.model!r}, "
                f"calls={self.tracker.calls})"
            )

    @property
    def remaining_usd(self) -> float:
        return max(0.0, self.usd - self.tracker.total_usd)

    @property
    def exceeded(self) -> bool:
        return self.tracker.total_usd >= self.usd
