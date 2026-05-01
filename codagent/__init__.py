"""codagent — plug-in harness system for agentic frameworks.

codagent makes it trivial to add behavioral contracts and domain-agent
supervisors to LLM-based applications built on LangChain, LangGraph,
CrewAI, AutoGen, or raw OpenAI/Anthropic clients.

Three orthogonal axes:

    Sources of harnesses:    HarnessSource (markdown, Guardrails.ai, NeMo, ...)
    Behavioral primitives:   Contract (the rule itself)
    Application targets:     ApplyTarget (where the rule lives at runtime)

The same Contract object can power:
    - LangChain callback handler  (HarnessCallbackHandler)
    - LangGraph node              (assumption_surface_node, verification_gate)
    - OpenAI / Anthropic wrap     (wrap_openai)
    - File output                 (apply_to_claude_code, apply_to_cursor, ...)

Built-in contracts (codagent.builtin):
    AssumptionSurface, VerificationLoop  — Karpathy core
    ToolCallSurface                      — tool-use agents
    RefusalPattern, CitationRequired     — domain compliance
    MetaAgentContract                    — domain agent as harness
"""

from codagent._abc import ApplyTarget, Contract, HarnessSource
from codagent._harness import Harness
from codagent.builtin import (
    AssumptionSurface,
    CitationRequired,
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
__version__ = "0.2.0"
