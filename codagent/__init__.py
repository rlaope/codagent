"""codagent — production utilities for LangGraph agent applications.

Modules:

    codagent.nodes          node wrappers (retry, timeout, cache, structured)
    codagent.tools          tool decorators (validated, circuit, rate_limit)
    codagent.observability  cost / step / trace primitives
    codagent.harness        behavior contracts (assumption surface,
                            verification, refusal, meta-agent, ...)

The harness module is the original codagent surface; everything that
used to be importable as ``from codagent import X`` lives now under
``codagent.harness.X``. Re-exports at this top level remain for one
minor cycle with a DeprecationWarning.
"""

from __future__ import annotations

import warnings as _warnings

# Public re-export: harness API still importable from codagent.* with a warning.
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
    # Re-exported from codagent.harness for one deprecation cycle.
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
__version__ = "0.3.0"
