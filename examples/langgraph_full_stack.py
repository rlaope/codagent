"""End-to-end example using nodes + tools + observability + harness.

This example simulates a tiny LangGraph-style flow without requiring
LangGraph or any LLM provider — every "LLM call" is a fake function so
the example runs offline.

What it demonstrates:
  - Stack node wrappers: with_retry + with_timeout + with_cache
  - Decorate a tool: validated_tool + circuit_breaker + rate_limit
  - Track cost with CostTracker, bound steps with StepBudget
  - Trace step shapes with StateTracer
  - Apply a harness contract: AssumptionSurface system addendum
"""

from __future__ import annotations

import random

from codagent.harness import AssumptionSurface, Harness
from codagent.nodes import with_cache, with_retry, with_timeout
from codagent.observability import CostTracker, StateTracer, StepBudget
from codagent.tools import circuit_breaker, rate_limit, validated_tool


# -- a fake "LLM call" with occasional transient failures -------------------

def _flaky_llm(state: dict) -> dict:
    if random.random() < 0.3:
        raise ConnectionError("simulated transient")
    return {
        **state,
        "answer": f"Echo: {state.get('query', '')}",
        "_tokens_in": 120,
        "_tokens_out": 40,
    }


# -- a fake tool we want to harden ------------------------------------------

def _validate_search(kw: dict) -> dict:
    if not kw.get("query"):
        raise ValueError("query is required")
    if not isinstance(kw.get("limit", 5), int):
        raise ValueError("limit must be int")
    return {"query": kw["query"], "limit": int(kw.get("limit", 5))}


@validated_tool(_validate_search)
@circuit_breaker(failure_threshold=3, reset_after=10)
@rate_limit(per_second=20)
def search_db(query: str, limit: int = 5) -> list[str]:
    return [f"{query}-result-{i}" for i in range(limit)]


def main() -> None:
    random.seed(42)

    # 1. Compose a harness
    harness = Harness.compose(AssumptionSurface(min_items=2))
    print(f"harness contracts: {[c.name for c in harness.contracts]}")
    print()

    # 2. Build a node stack: cache > retry > (raw)
    cached_retry_node = with_cache(
        with_retry(_flaky_llm, attempts=5, backoff=0.001),
        key_fn=lambda s: s.get("query"),
    )

    # Wrap with timeout for safety
    final_node = with_timeout(cached_retry_node, seconds=5.0)

    # 3. Trace it
    tracer = StateTracer()
    traced_node = tracer.wrap_node(final_node, name="llm_step")

    # 4. Track cost & budget
    budget = StepBudget(max_steps=10)
    cost = CostTracker(model="gpt-4o-mini")

    # 5. Run a few "turns" through the node
    for q in ["hello", "world", "hello", "again"]:
        budget.step()
        result = traced_node({"query": q})
        cost.record_call(
            input_tokens=result.get("_tokens_in", 0),
            output_tokens=result.get("_tokens_out", 0),
        )
        print(f"  q={q!r:<10} answer={result['answer']!r}")

    print()
    print(f"steps used: {budget.steps}/{budget.max_steps} (remaining {budget.remaining()})")
    print(f"cost: {cost!r}")
    print(f"trace: {len(tracer)} steps recorded")
    print()

    # 6. Tool: validated, circuit-broken, rate-limited
    out = search_db(query="python", limit=3)
    print(f"search_db ok: {out}")

    try:
        search_db(query="")
    except ValueError as e:
        print(f"validation rejected empty query: {e}")


if __name__ == "__main__":
    main()
