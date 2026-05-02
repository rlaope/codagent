"""codagent.integrations — adapters for the Python LLM-agent ecosystem.

One harness, many places to plug it in. Each integration takes a
``Harness`` (composed from any mix of contracts and sources) and wires
it into a specific framework's call site.

Real integrations (working):
    wrap_openai           OpenAI Python SDK >= 1.0
    wrap_anthropic        Anthropic Python SDK >= 0.30
    pydantic_ai_prompt    System-prompt helper for Pydantic AI Agent
    HarnessRunnable       LangChain Runnable wrapper
    make_harness_callback_handler  LangChain BaseCallbackHandler factory
    assumption_surface_node        LangGraph node factory
    verification_gate              LangGraph conditional-edge fn

Stubs (placeholder, contributions welcome):
    crewai, autogen, dspy, llamaindex
"""

# Re-export framework adapters from existing harness submodule for a
# unified import surface, plus new ones in this package.
from codagent.harness.targets.openai_client import unwrap_openai, wrap_openai
from codagent.integrations.anthropic_client import unwrap_anthropic, wrap_anthropic
from codagent.integrations.pydantic_ai import pydantic_ai_prompt

# LangChain / LangGraph (re-exports)
from codagent.harness.langchain_integration import (  # noqa: F401
    HarnessRunnable,
    make_harness_callback_handler,
)
from codagent.harness.langgraph_nodes import (  # noqa: F401
    assumption_surface_node,
    verification_gate,
)

__all__ = [
    "HarnessRunnable",
    "assumption_surface_node",
    "make_harness_callback_handler",
    "pydantic_ai_prompt",
    "unwrap_anthropic",
    "unwrap_openai",
    "verification_gate",
    "wrap_anthropic",
    "wrap_openai",
]

# LlamaIndex callback (optional dep)
try:
    from codagent.integrations.llamaindex import HarnessLlamaIndexCallback  # noqa: F401
    __all__.append("HarnessLlamaIndexCallback")
except Exception:
    pass
