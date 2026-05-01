# codagent

[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)

**Production utilities for Python LLM agents.**

`codagent` is a small library for the patterns that every Python team
ends up writing when they ship LLM agents — regardless of which
framework they use:

- **Composable node wrappers** (retry, timeout, cache, structured output)
- **Tool decorators** (validation, circuit breaker, rate limit)
- **Observability primitives** (cost, step, trace)
- **Behavior contracts** (assumption surface, refusal patterns,
  citation enforcement, LLM-as-judge supervisors)

Works with **LangGraph**, **LangChain**, **LlamaIndex**, **CrewAI**,
**AutoGen**, **DSPy**, **Pydantic AI**, or raw **OpenAI** /
**Anthropic** clients. The core is framework-agnostic; framework-specific
adapters live in `codagent.integrations`.

## Why this exists

Every Python team building production LLM agents writes the same glue:

- Retry on transient API errors
- Circuit-break on flaky tools
- Track tokens and cost
- Force the model to surface its assumptions
- Stop "should work" claims without evidence
- Refuse sensitive prompts with a structured block
- Run a domain supervisor agent over every response

Each of these is a few lines, but the few-lines-per-team adds up across
hundreds of repos. `codagent` packages them once.

## Install

```bash
pip install git+https://github.com/rlaope/codagent.git
```

> **Python 3.14 note.** Editable installs (`pip install -e`) currently
> fail to import on Python 3.14 because setuptools writes
> `__editable__.codagent-*.pth`, and 3.14 skips `.pth` files whose name
> starts with `_` as hidden. Use a regular install (`pip install
> /path/to/codagent`) on 3.14, or stay on Python 3.13 / 3.12 for
> editable workflows. Tracked at upstream pypa/setuptools.

Optional integrations (install only what your stack needs):

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

## What's in the library

```
codagent/
├── nodes/              composable node wrappers
│   with_retry, with_timeout, with_cache, parse_structured
│
├── tools/              tool callable hardening
│   validated_tool, circuit_breaker, rate_limit
│
├── observability/      production tracking
│   CostTracker, StepBudget, StateTracer
│
├── harness/            behavior contracts
│   Harness composer, 6 built-in contracts (Assumption Surface,
│   Verification Loop, Tool Call Surface, Refusal Pattern,
│   Citation Required, MetaAgent Contract)
│
└── integrations/       Python LLM ecosystem adapters
    wrap_openai, wrap_anthropic, pydantic_ai_prompt,
    HarnessRunnable (LangChain), assumption_surface_node (LangGraph),
    HarnessLlamaIndexCallback, crewai/autogen/dspy stubs
```

## Quick start

### OpenAI / Anthropic raw client

```python
from openai import OpenAI
from anthropic import Anthropic
from codagent.harness import AssumptionSurface, VerificationLoop
from codagent.integrations import wrap_openai, wrap_anthropic

oai = wrap_openai(OpenAI(), AssumptionSurface(), VerificationLoop())
ant = wrap_anthropic(Anthropic(), AssumptionSurface(), VerificationLoop())
# Both clients now inject the harness addendum into every call.
```

### LangChain

```python
from langchain_openai import ChatOpenAI
from codagent.harness import Harness, AssumptionSurface
from codagent.integrations import HarnessRunnable

chain = HarnessRunnable(
    Harness.compose(AssumptionSurface(min_items=2)),
    ChatOpenAI(model="gpt-4o"),
)
```

### LangGraph

```python
from codagent.integrations import assumption_surface_node, verification_gate

graph.add_node("clarify", assumption_surface_node(my_llm, min_items=3))
graph.add_conditional_edges("execute", verification_gate, {"verified": "done", "missing": "retry"})
```

### Pydantic AI

```python
from pydantic_ai import Agent
from codagent.harness import Harness, CitationRequired
from codagent.integrations import pydantic_ai_prompt

h = Harness.compose(CitationRequired(min_citations=1))
agent = Agent(
    "openai:gpt-4o",
    system_prompt=pydantic_ai_prompt(h, base="You are a research assistant."),
)
result = agent.run_sync("Summarize the latest in transformer scaling")
print(h.validate(str(result.data)))
```

### LlamaIndex

```python
from llama_index.core import Settings
from codagent.harness import Harness, AssumptionSurface
from codagent.integrations import HarnessLlamaIndexCallback

Settings.callback_manager = CallbackManager([
    HarnessLlamaIndexCallback(Harness.compose(AssumptionSurface()))
])
```

### Production hardening (any framework)

```python
from codagent.nodes import with_retry, with_cache
from codagent.tools import circuit_breaker, rate_limit
from codagent.observability import CostTracker, StepBudget

# Stack node wrappers
robust_node = with_retry(
    with_cache(my_llm_call, key_fn=lambda s: s["query"], ttl=300),
    attempts=3,
    on=(ConnectionError,),
)

# Decorate tools
@circuit_breaker(failure_threshold=5, reset_after=60)
@rate_limit(per_second=10)
def search_db(query: str): ...

# Track cost + bound steps
budget = StepBudget(max_steps=20)
with CostTracker(model="gpt-4o") as cost:
    result = run_my_agent(...)
print(f"${cost.total_usd:.4f} over {cost.calls} calls")
```

## Built-in behavior contracts

| Contract | Forces |
|---|---|
| `AssumptionSurface` | leading `Assumptions:` block when request is ambiguous |
| `VerificationLoop` | evidence (test, output, diff) before any "done" claim |
| `ToolCallSurface` | explicit `ToolCall:` block before tool invocation |
| `RefusalPattern` | structured `Refusal:` block on sensitive keywords |
| `CitationRequired` | `[source: ...]` markers on factual claims |
| `MetaAgentContract` | LLM-as-judge validation by a supervisor agent |

Compose them: `Harness.compose(AssumptionSurface(), CitationRequired(), ...)`.

## End-to-end example

[`examples/langgraph_full_stack.py`](examples/langgraph_full_stack.py)
combines node wrappers + tool decorators + observability + harness in
one runnable script (offline — no API keys required).

## Status

`v0.4.0` alpha. Core is stable; framework adapters expand as the
ecosystem evolves.

## License

MIT — see [LICENSE](./LICENSE).
