"""codagent.observability — cost / step / trace primitives.

    CostTracker     accumulate token usage and compute USD cost
    BudgetCap       hard USD ceiling on a CostTracker
    StepBudget      raise BudgetExceeded after N steps
    StepCounter     plain counter
    StateTracer     wrap a node and record before/after state shape
"""

from codagent.observability.budget import BudgetCap
from codagent.observability.cost import CostTracker, MODEL_PRICES
from codagent.observability.steps import (
    BudgetExceeded,
    StepBudget,
    StepCounter,
)
from codagent.observability.trace import StateTracer

__all__ = [
    "BudgetCap",
    "BudgetExceeded",
    "CostTracker",
    "MODEL_PRICES",
    "StateTracer",
    "StepBudget",
    "StepCounter",
]
