# Production Hardening

Stack node wrappers, tool decorators, observability, and harness contracts for a production-grade agent.

## Overview

This guide shows how to combine all codagent modules in one runnable agent. The example uses LangGraph, but the patterns apply to any framework.

## Full-stack example

```python
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from codagent.nodes import with_retry, with_timeout, with_cache
from codagent.tools import validated_tool, circuit_breaker, rate_limit
from codagent.observability import CostTracker, StepBudget, StateTracer
from codagent.harness import Harness, AssumptionSurface, VerificationLoop, ToolCallSurface
from codagent.integrations import wrap_openai, assumption_surface_node, verification_gate

# ========== 1. OBSERVABILITY ==========

cost = CostTracker(model="gpt-4o")
budget = StepBudget(max_steps=20)
tracer = StateTracer()

# ========== 2. HARNESS ==========

harness = Harness.compose(
    AssumptionSurface(min_items=2),
    VerificationLoop(),
    ToolCallSurface(),
)

# ========== 3. LLM CLIENT ==========

llm = wrap_openai(ChatOpenAI(model="gpt-4o"), *harness.contracts)

# ========== 4. TOOL HARDENING ==========

class SearchArgs(BaseModel):
    query: str
    limit: int = 10

def validate_search_args(kwargs):
    args = SearchArgs(**kwargs)
    if args.limit < 1 or args.limit > 100:
        raise ValueError("limit must be 1-100")
    return args.model_dump()

@validated_tool(validate_search_args)
@circuit_breaker(failure_threshold=5, reset_after=60)
@rate_limit(per_second=10)
def search_documents(query: str, limit: int = 10) -> str:
    # Simulated document search
    return f"Found {limit} documents matching '{query}'"

# ========== 5. NODE WRAPPERS ==========

def llm_node(state):
    """Call the LLM with harness addendum."""
    messages = state.get("messages", [])
    response = llm.chat.completions.create(
        model="gpt-4o",
        messages=messages,
    )
    text = response.choices[0].message.content
    
    # Record cost
    usage = response.usage
    cost.record_call(
        input_tokens=usage.prompt_tokens,
        output_tokens=usage.completion_tokens,
    )
    
    return {"messages": [..., {"role": "assistant", "content": text}]}

# Wrap with robustness
robust_llm = with_retry(
    with_timeout(
        with_cache(
            llm_node,
            key_fn=lambda s: s.get("query", "default"),
            ttl=300,
        ),
        seconds=30,
    ),
    attempts=3,
    backoff=1.0,
    on=(ConnectionError, TimeoutError),
)

# Wrap with tracing
traced_llm = tracer.wrap_node(robust_llm, name="llm_call")

# ========== 6. LANGGRAPH ASSEMBLY ==========

def tool_node(state):
    """Process tool calls from the LLM."""
    messages = state.get("messages", [])
    last = messages[-1] if messages else {}
    
    if "search_documents" in str(last.get("content", "")):
        result = search_documents(query="test", limit=5)
        return {"tool_result": result}
    
    return {"tool_result": ""}

graph = StateGraph(state_keys=["messages", "tool_result", "done"])

# Add nodes
graph.add_node("clarify", assumption_surface_node(ChatOpenAI(model="gpt-4o"), min_items=2))
graph.add_node("query", traced_llm)
graph.add_node("tools", tracer.wrap_node(tool_node, name="tool_call"))
graph.add_node("verify", lambda s: {})

# Wire edges
graph.add_edge(START, "clarify")
graph.add_edge("clarify", "query")
graph.add_edge("query", "tools")
graph.add_conditional_edges(
    "tools",
    verification_gate,
    {"verified": END, "missing": "query"},
)

compiled = graph.compile()

# ========== 7. EXECUTION WITH GUARDS ==========

state = {
    "messages": [{"role": "user", "content": "Find documents about Python"}],
}

try:
    while not state.get("done"):
        budget.step()  # Guard against infinite loops
        state = compiled.invoke(state)

except Exception as e:
    print(f"Error: {e}")
    state["error"] = str(e)

# ========== 8. REPORTING ==========

print("=== EXECUTION REPORT ===")
print(f"Steps executed: {budget.steps}")
print(f"Cost: ${cost.total_usd:.4f} ({cost.total_tokens} tokens)")
print(f"Traces: {len(tracer)} steps recorded")
print()
print("Trace summary:")
for step in tracer.steps:
    print(f"  {step['name']}: {step['duration_seconds']:.2f}s")

print()
print("Validation result:")
final_msg = state.get("messages", [{}])[-1].get("content", "")
result = harness.validate(final_msg)
for name, check in result.items():
    if name != "all_ok":
        status = "PASS" if check["ok"] else "FAIL"
        print(f"  {name}: {status}")
        if not check["ok"]:
            print(f"    Reason: {check['reason']}")
```

## Piece by piece

### 1. Observability setup

```python
from codagent.observability import CostTracker, StepBudget, StateTracer

# Track cost
cost = CostTracker(model="gpt-4o")

# Guard against runaway loops
budget = StepBudget(max_steps=20)

# Record execution traces
tracer = StateTracer()
```

### 2. Harness composition

```python
from codagent.harness import Harness, AssumptionSurface, VerificationLoop, ToolCallSurface

harness = Harness.compose(
    AssumptionSurface(min_items=2),
    VerificationLoop(),
    ToolCallSurface(),
)
```

### 3. Inject harness into LLM client

```python
from openai import OpenAI
from codagent.integrations import wrap_openai

llm = wrap_openai(OpenAI(), *harness.contracts)
# Now every chat.completions.create() call includes the harness addendum
```

### 4. Harden tools

```python
from codagent.tools import validated_tool, circuit_breaker, rate_limit

@validated_tool(my_validator)
@circuit_breaker(failure_threshold=5, reset_after=60)
@rate_limit(per_second=10)
def my_tool(arg: str) -> str:
    pass
```

### 5. Wrap nodes with robustness

```python
from codagent.nodes import with_retry, with_timeout, with_cache

robust = with_retry(
    with_timeout(
        with_cache(my_node, key_fn=..., ttl=300),
        seconds=30,
    ),
    attempts=3,
    backoff=1.0,
    on=(ConnectionError,),
)

traced = tracer.wrap_node(robust, name="my_node")
```

### 6. Execute with guards

```python
state = {}
while not state.get("done"):
    try:
        budget.step()  # Raises BudgetExceeded if exceeded
    except BudgetExceeded:
        print("Stopping: step budget exhausted")
        break
    
    state = graph.invoke(state)
    
    # Record cost if you capture tokens
    cost.record_call(input_tokens=100, output_tokens=50)
```

### 7. Report

```python
print(f"Steps: {budget.steps}")
print(f"Cost: ${cost.total_usd:.4f}")
print(f"Traces: {len(tracer)}")
for step in tracer.steps:
    print(f"  {step['name']}: {step['duration_seconds']}s")

# Validate final output
result = harness.validate(final_response_text)
if not result["all_ok"]:
    print("WARNING: Some contracts failed")
    for name, check in result.items():
        if not check["ok"]:
            print(f"  {name}: {check['reason']}")
```

## When to use what

| Component | When | Example |
|-----------|------|---------|
| `with_retry` | Network is flaky | LLM API calls, database queries |
| `with_timeout` | You need a hard deadline | LLM inference must finish in 30s |
| `with_cache` | Results are expensive and repeated | Embedding lookups, semantic search |
| `validated_tool` | Tool inputs are user-provided | LLM tool calling |
| `circuit_breaker` | Downstream service is flaky | External API, database |
| `rate_limit` | You need throughput control | API quota limits, cost control |
| `CostTracker` | You track spending | Logging token usage for billing |
| `StepBudget` | Agent loops can runaway | ReAct agents, multi-turn loops |
| `StateTracer` | You need execution visibility | Debugging, performance analysis |
| `AssumptionSurface` | Requests are ambiguous | User-facing agents |
| `VerificationLoop` | You require evidence | Code generation, report writing |
| `ToolCallSurface` | Agent uses tools | Tool-use agents, function calling |
| `RefusalPattern` | Request may be sensitive | Finance, healthcare, legal |
| `CitationRequired` | Claims must be sourced | Research, legal, compliance |
| `MetaAgentContract` | Rule is nuanced | Domain-specific compliance |

---

## See also

- [Nodes](../modules/nodes.md)
- [Tools](../modules/tools.md)
- [Observability](../modules/observability.md)
- [Harness](../modules/harness.md)
- [LangGraph Framework](../frameworks/langgraph.md)
