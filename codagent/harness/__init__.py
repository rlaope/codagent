"""codagent.harness — behavior contracts for LLM calls.

The harness is one module of the codagent utility library. It provides
runtime behavior contracts (assumption surfacing, verification, tool
intent declaration, refusal patterns, citations, meta-agent supervisors)
that compose via the Harness object and apply to OpenAI clients,
LangChain Runnables, LangGraph nodes, or output files.

Public API:

    from codagent.harness import (
        Harness,
        Contract,
        HarnessSource,
        ApplyTarget,
        AssumptionSurface,
        VerificationLoop,
        ToolCallSurface,
        RefusalPattern,
        CitationRequired,
        MetaAgentContract,
    )
"""

from codagent.harness._abc import ApplyTarget, Contract, HarnessSource
from codagent.harness._harness import Harness
from codagent.harness.builtin import (
    AssumptionSurface,
    CitationRequired,
    FaithfulnessContract,
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
    "FaithfulnessContract",
    "Harness",
    "HarnessSource",
    "MetaAgentContract",
    "RefusalPattern",
    "ToolCallSurface",
    "VerificationLoop",
]
