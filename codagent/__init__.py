"""codagent — production utilities for LangGraph agent applications.

Modules:

    codagent.nodes          node wrappers (retry, timeout, cache, structured)
    codagent.tools          tool decorators (validated, circuit, rate_limit)
    codagent.observability  cost / step / trace primitives
    codagent.harness        behavior contracts (assumption surface,
                            verification, refusal, meta-agent, ...)

The harness module is the original codagent surface; everything that
used to be importable as ``from codagent import X`` lives now under
``codagent.harness.X``. The names below are re-exported at this top
level for backward compatibility with pre-0.4 imports.
"""

from __future__ import annotations

from codagent.harness import (
    ApplyTarget,
    AssumptionSurface,
    CitationRequired,
    Contract,
    Harness,
    HarnessSource,
    MetaAgentContract,
    RefusalPattern,
    ToolCallSurface,
    VerificationLoop,
)


__all__ = [
    "ApplyTarget",
    "AssumptionSurface",
    "CitationRequired",
    "Contract",
    "Harness",
    "HarnessSource",
    "MetaAgentContract",
    "RefusalPattern",
    "ToolCallSurface",
    "VerificationLoop",
]
__version__ = "0.5.0"
