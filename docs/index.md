# codagent

Production utilities for Python LLM agents.

`codagent` is a small library for the patterns every Python team writes when shipping LLM agents, regardless of which framework they use. It provides composable node wrappers, tool decorators, observability primitives, and behavior contracts.

## Who it's for

Teams building production LLM agents in Python who use LangGraph, LangChain, LlamaIndex, CrewAI, AutoGen, DSPy, Pydantic AI, or raw OpenAI/Anthropic clients. The core is framework-agnostic; framework-specific adapters live in `codagent.integrations`.

## The 5 modules

**Nodes** — Composable wrappers for node callables: `with_retry`, `with_timeout`, `with_cache`, `parse_structured`. Stack them freely on any state-to-state callable.

**Tools** — Decorators for hardening tool callables: `validated_tool`, `circuit_breaker`, `rate_limit`. Includes exception types like `CircuitBreakerOpen` and `RateLimitExceeded`.

**Observability** — Production tracking primitives: `CostTracker` (token usage and USD), `StepBudget`/`StepCounter` (loop guards), `StateTracer` (per-node execution logs).

**Harness** — Behavior contracts and composer. Build via `Harness.compose(...)` mixing contracts like `AssumptionSurface`, `VerificationLoop`, `ToolCallSurface`, `RefusalPattern`, `CitationRequired`, `MetaAgentContract`. Apply to OpenAI clients, LangChain Runnables, LangGraph nodes, or output files.

**Integrations** — Framework-specific adapters. Nine working adapters (OpenAI, Anthropic, LangChain, LangGraph, Pydantic AI, LlamaIndex) plus stubs for CrewAI, AutoGen, DSPy.

## Quick start

```python
from openai import OpenAI
from codagent.harness import AssumptionSurface, VerificationLoop
from codagent.integrations import wrap_openai

# Wrap an OpenAI client with behavior contracts
client = wrap_openai(
    OpenAI(),
    AssumptionSurface(min_items=2),
    VerificationLoop(),
)

# Every API call now injects the harness addendum into the system prompt
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Add an export feature"}],
)
```

See [Getting Started](getting-started.md) for a 5-minute walkthrough covering node wrappers, tool decorators, cost tracking, and validation.

## Module documentation

- [Nodes](modules/nodes.md) — `with_retry`, `with_timeout`, `with_cache`, `parse_structured`
- [Tools](modules/tools.md) — `validated_tool`, `circuit_breaker`, `rate_limit`
- [Observability](modules/observability.md) — `CostTracker`, `StepBudget`, `StepCounter`, `StateTracer`
- [Harness](modules/harness.md) — Behavior contracts and `Harness` composer
- [Integrations](modules/integrations.md) — Overview of framework adapters

## Framework guides

- [OpenAI](frameworks/openai.md)
- [Anthropic](frameworks/anthropic.md)
- [LangChain](frameworks/langchain.md)
- [LangGraph](frameworks/langgraph.md)
- [LlamaIndex](frameworks/llamaindex.md)
- [Pydantic AI](frameworks/pydantic-ai.md)

## Production guides

- [Production Hardening](guides/production-hardening.md) — Stack nodes + tools + observability + harness
- [Behavior Contracts](guides/behavior-contracts.md) — When to use which contract; composing custom ones
- [Meta-Agent Supervisor](guides/meta-agent-supervisor.md) — Domain compliance with LLM-as-judge

## Version

`v0.4.0` alpha. Core is stable; framework adapters expand as the ecosystem evolves. See [CHANGELOG](CHANGELOG.md) for version history.

## Install

```bash
pip install git+https://github.com/rlaope/codagent.git
```

Optional framework integrations:

```bash
pip install codagent[openai]         # OpenAI client wrap
pip install codagent[anthropic]      # Anthropic client wrap
pip install codagent[langchain]      # LangChain callback + Runnable
pip install codagent[langgraph]      # LangGraph node factories
pip install codagent[llamaindex]     # LlamaIndex callback handler
pip install codagent[pydantic-ai]    # Pydantic AI system-prompt helper
pip install codagent[crewai]         # CrewAI agent backstory adapter
pip install codagent[autogen]        # AutoGen system-message adapter
pip install codagent[dspy]           # DSPy module wrapper
pip install codagent[guardrails-ai]  # wrap Guardrails.ai validators
pip install codagent[nemo]           # wrap NeMo Guardrails flows
```

## License

MIT.
