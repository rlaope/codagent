# codagent

[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)

**Production utilities for LangGraph agent applications.**

`codagent` is a small library of composable wrappers, decorators, and
primitives that LangGraph product teams currently hand-roll: retry /
timeout / cache wrappers around nodes, validation / circuit-breaker /
rate-limit decorators around tools, cost & step tracking, plus a
behavior-contract module for assumption-surfacing, refusals, and
LLM-as-judge supervision.

> Lodash for LangGraph product development.

## Why this exists

The LangGraph ecosystem (late 2025 / early 2026) has frameworks
(`langgraph-agent-toolkit`) and scaffolds (`langgraph-starter-kit`),
but **no library that ships small composable utility primitives**:

- LangGraph's native `retry_policy` silently drops some exceptions
  ([#6027](https://github.com/langchain-ai/langgraph/issues/6027))
- No tool circuit breaker / rate limiter as packages
- No cost-budget guard primitive
- No state-reducer library beyond `operator.add`
- `langgraph-supervisor` is soft-deprecated

Every team running production LangGraph agents writes the same glue.
`codagent` packages it.

## Install

```bash
pip install git+https://github.com/rlaope/codagent.git
```

Optional integrations:

```bash
pip install codagent[langchain]      # LangChain callback handler + Runnable
pip install codagent[openai]         # OpenAI client wrapper
pip install codagent[anthropic]      # Anthropic client wrapper (planned)
pip install codagent[guardrails-ai]  # wrap Guardrails.ai validators
pip install codagent[nemo]           # wrap NeMo Guardrails flows
```

## What's in v0.3.0

```
codagent/
├── nodes/              # composable node wrappers
│   ├── with_retry      # retry on listed exception types with backoff
│   ├── with_timeout    # cross-platform wall-clock timeout
│   ├── with_cache      # LRU cache with custom key_fn + TTL
│   └── parse_structured  # parse output through any validator
│
├── tools/              # tool callable hardening
│   ├── validated_tool  # kwargs validation before invocation
│   ├── circuit_breaker # 3-state breaker with cooldown
│   └── rate_limit      # sliding-window rate limit
│
├── observability/      # production tracking
│   ├── CostTracker     # token & USD accumulator (OpenAI/Anthropic price table)
│   ├── StepBudget      # raises BudgetExceeded after max_steps
│   └── StateTracer     # before/after state shape + duration per node
│
└── harness/            # behavior contracts (former codagent core)
    ├── AssumptionSurface, VerificationLoop, ToolCallSurface
    ├── RefusalPattern, CitationRequired
    └── MetaAgentContract  # LLM-as-judge for nuanced compliance
```

## Quick start — node wrappers

```python
from codagent.nodes import with_retry, with_timeout, with_cache

# Stack wrappers freely
node = with_timeout(
    with_retry(
        with_cache(my_llm_node, key_fn=lambda s: s["query"], ttl=300),
        attempts=3,
        on=(ConnectionError, TimeoutError),
    ),
    seconds=30,
)

graph.add_node("step", node)
```

## Quick start — tool hardening

```python
from codagent.tools import validated_tool, circuit_breaker, rate_limit
from pydantic import BaseModel

class SearchArgs(BaseModel):
    query: str
    limit: int = 10

@validated_tool(lambda kw: SearchArgs(**kw).model_dump())
@circuit_breaker(failure_threshold=5, reset_after=60)
@rate_limit(per_second=10)
def search_db(query: str, limit: int = 10) -> list:
    ...
```

## Quick start — cost & budget

```python
from codagent.observability import CostTracker, StepBudget, StateTracer

tracer = StateTracer()
budget = StepBudget(max_steps=20)
with CostTracker(model="gpt-4o") as cost:
    for step in run_loop():
        budget.step()
        traced = tracer.wrap_node(step.node)
        result = traced(state)
        cost.record_call(
            input_tokens=result.get("_in", 0),
            output_tokens=result.get("_out", 0),
        )

print(f"cost ${cost.total_usd:.4f} over {cost.calls} calls, {len(tracer)} traced steps")
```

## Quick start — harness contracts

```python
from codagent.harness import (
    Harness, AssumptionSurface, RefusalPattern, MetaAgentContract,
)

harness = Harness.compose(
    AssumptionSurface(min_items=2),
    RefusalPattern(sensitive_keywords=("medical-advice",)),
    MetaAgentContract(
        name="finance-compliance",
        judge_callable=my_anthropic_judge,
        judge_prompt_template="Check disclaimer in: {response}",
    ),
)

# Inject the system addendum into your messages
augmented = harness.wrap_messages(messages)

# Validate a response
result = harness.validate(model_output)
# {'AssumptionSurface': {'ok': ...}, 'RefusalPattern': {...}, ..., 'all_ok': bool}
```

## End-to-end example

See [`examples/langgraph_full_stack.py`](examples/langgraph_full_stack.py)
— combines node wrappers + tool decorators + observability + harness in
one runnable script. No API keys required (uses fake LLM stubs).

## Migration from v0.2.0

Top-level imports still work with a `DeprecationWarning`:

```python
# v0.2.0 (still works through v0.3.x)
from codagent import AssumptionSurface, Harness

# v0.3.0 recommended
from codagent.harness import AssumptionSurface, Harness
```

The top-level shim will be removed in v0.4.0.

## Status

`v0.3.0` alpha. 75 tests passing. Core abstracts stable in spirit.
PRs welcome — see [CONTRIBUTING.md](./CONTRIBUTING.md).

Roadmap:
- v0.4.0: `codagent.state` (reducers), `codagent.multi_agent` (supervisor patterns)
- v0.5.0: `codagent.memory`, `codagent.rag`, `codagent.testing`

## License

MIT — see [LICENSE](./LICENSE). Karpathy-derived ideas attributed there.
