"""codagent — runtime behavior contracts for LLM agents.

Two composable primitives:
    AssumptionSurface — forces declarative assumptions before action
    VerificationLoop — forces evidence before "done" claims

See https://github.com/rlaope/codagent
"""

from codagent.core import (
    AssumptionSurface,
    VerificationLoop,
    Harness,
)

__all__ = ["AssumptionSurface", "VerificationLoop", "Harness"]
__version__ = "0.0.1"
