"""``StepBudget`` / ``StepCounter`` — guard against runaway loops."""

from __future__ import annotations

from dataclasses import dataclass


class BudgetExceeded(Exception):
    """Raised when a StepBudget is incremented past its max."""


@dataclass
class StepBudget:
    """Counter that raises when it crosses ``max_steps``.

    Call ``step()`` before each major operation. The first call returns
    1; the (max_steps + 1)-th call raises ``BudgetExceeded``.
    """

    max_steps: int
    steps: int = 0

    def step(self) -> int:
        self.steps += 1
        if self.steps > self.max_steps:
            raise BudgetExceeded(
                f"step budget {self.max_steps} exceeded "
                f"(would be step #{self.steps})"
            )
        return self.steps

    def remaining(self) -> int:
        return max(0, self.max_steps - self.steps)


@dataclass
class StepCounter:
    """Plain step counter without a hard limit."""

    count: int = 0

    def increment(self) -> int:
        self.count += 1
        return self.count
