"""codagent.tools — decorators for hardening tool callables.

Each decorator can be stacked:

    @validated_tool(SearchArgs)
    @circuit_breaker(failure_threshold=5, reset_after=60)
    @rate_limit(per_second=10)
    def search_db(query: str, limit: int = 10): ...
"""

from codagent.tools.circuit import (
    CircuitBreakerOpen,
    CircuitState,
    circuit_breaker,
)
from codagent.tools.rate_limit import RateLimitExceeded, rate_limit
from codagent.tools.validate import validated_tool

__all__ = [
    "CircuitBreakerOpen",
    "CircuitState",
    "RateLimitExceeded",
    "circuit_breaker",
    "rate_limit",
    "validated_tool",
]
