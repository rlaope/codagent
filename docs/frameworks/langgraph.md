# LangGraph Framework Guide

Wrap LangGraph nodes and conditional edges with codagent primitives.

## Setup

Install:

```bash
pip install codagent[langgraph]
```

## `assumption_surface_node`

Returns a LangGraph node callable that asks the LLM for assumptions.

**Signature:**

```python
def assumption_surface_node(llm, *, min_items: int = 1) -> Callable:
    """Return a LangGraph node callable that asks the LLM for assumptions."""
```

**Arguments:**

- `llm`: Any LangChain LLM or chat model
- `min_items`: Minimum assumptions required

**Returns:** A callable with signature `node(state) -> dict`.

## Example

```python
from langgraph.graph import StateGraph
from langchain_openai import ChatOpenAI
from codagent.integrations import assumption_surface_node

# Create a state graph
graph = StateGraph(...)

# Add an assumption surface node early in the graph
graph.add_node(
    "clarify",
    assumption_surface_node(ChatOpenAI(model="gpt-4o"), min_items=2),
)

# Wire it into your graph
graph.add_edge("start", "clarify")
graph.add_edge("clarify", "process")
```

The node will automatically:
1. Extract the existing messages from state
2. Prepend a system message forcing assumptions
3. Return an updated state with the assumption system message

## `verification_gate`

Conditional-edge function that returns `"verified"` or `"missing"` based on whether the state contains evidence.

**Signature:**

```python
def verification_gate(
    state,
    *,
    evidence_field: str = "evidence"
) -> str:
    """Conditional-edge function: 'verified' if state has evidence, else 'missing'."""
```

**Arguments:**

- `state`: Graph state dict
- `evidence_field`: State key to check for explicit evidence

**Returns:** `"verified"` or `"missing"`.

## Example with conditional edges

```python
from langgraph.graph import StateGraph
from langchain_openai import ChatOpenAI
from codagent.integrations import verification_gate, assumption_surface_node

def execute_node(state):
    # Do something, return result
    return {"result": "done"}

graph = StateGraph(...)

# Add nodes
graph.add_node("execute", execute_node)
graph.add_node("retry", lambda s: {"retry_count": s.get("retry_count", 0) + 1})
graph.add_node("done", lambda s: {"final": True})

# Add conditional edge using verification_gate
graph.add_conditional_edges(
    "execute",
    verification_gate,
    {
        "verified": "done",
        "missing": "retry",
    },
)

# Run the graph
result = graph.invoke({})
```

The gate checks:
1. If `state["evidence"]` is truthy, return `"verified"`
2. Otherwise, check the last message for evidence markers (test output, diffs, etc.)
3. Return `"verified"` if evidence found, `"missing"` otherwise

## Full example: assumptions + verification loop

```python
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from codagent.integrations import assumption_surface_node, verification_gate

def plan_node(state):
    """Generate a plan."""
    messages = state.get("messages", [])
    response = ChatOpenAI(model="gpt-4o").invoke(messages)
    return {"messages": [..., {"role": "assistant", "content": response.content}]}

def execute_node(state):
    """Execute the plan."""
    # Simulate execution with evidence
    return {
        "messages": state.get("messages", []) + [
            {
                "role": "user",
                "content": "I ran the tests and they all passed (exit code 0).",
            }
        ]
    }

# Build the graph
graph = StateGraph(state_keys=["messages"])

graph.add_node("clarify", assumption_surface_node(ChatOpenAI(model="gpt-4o"), min_items=2))
graph.add_node("plan", plan_node)
graph.add_node("execute", execute_node)
graph.add_node("done", lambda s: {"final": True})

# Wire edges
graph.add_edge(START, "clarify")
graph.add_edge("clarify", "plan")
graph.add_edge("plan", "execute")
graph.add_conditional_edges(
    "execute",
    verification_gate,
    {"verified": "done", "missing": "plan"},  # Retry if not verified
)
graph.add_edge("done", END)

# Compile and run
compiled = graph.compile()
result = compiled.invoke({"messages": [{"role": "user", "content": "Add an export feature"}]})

print(result)
```

## With node wrappers

Wrap individual nodes with `with_retry`, `with_timeout`, or `with_cache`:

```python
from langgraph.graph import StateGraph
from langchain_openai import ChatOpenAI
from codagent.nodes import with_retry, with_timeout
from codagent.integrations import assumption_surface_node

def my_node(state):
    response = ChatOpenAI(model="gpt-4o").invoke(state.get("messages", []))
    return {"response": response.content}

# Wrap with robustness
robust_node = with_retry(
    with_timeout(my_node, seconds=30),
    attempts=3,
    on=(ConnectionError,),
)

graph = StateGraph(...)
graph.add_node("query", robust_node)
```

## With observability

Combine with observability primitives:

```python
from langgraph.graph import StateGraph
from codagent.observability import CostTracker, StepBudget, StateTracer
from codagent.integrations import assumption_surface_node

# Set up observability
cost = CostTracker(model="gpt-4o")
budget = StepBudget(max_steps=10)
tracer = StateTracer()

def my_node(state):
    # ... implementation
    return updated_state

graph = StateGraph(...)
graph.add_node("step1", tracer.wrap_node(my_node, name="step1"))

# Run with guards
state = {}
while not state.get("done"):
    budget.step()  # Raises BudgetExceeded if exceeded
    state = graph.invoke(state)
    cost.record_call(input_tokens=100, output_tokens=50)

print(f"Steps: {budget.steps}, Cost: ${cost.total_usd:.4f}")
```

---

## See also

- [Harness Module](../modules/harness.md) — Contracts and composition
- [Nodes Module](../modules/nodes.md) — Node wrappers like `with_retry`, `with_timeout`
- [Observability Module](../modules/observability.md) — Cost tracking and step budgets
- [Getting Started](../getting-started.md) — 5-minute intro
- [Production Hardening](../guides/production-hardening.md) — Full stack example
