# Observability

Production tracking primitives: `CostTracker` (token usage and USD), `StepBudget`/`StepCounter` (loop guards), `StateTracer` (per-node execution logs).

## Overview

Observability tools help you understand and bound agent execution: how much it costs, how many steps it takes, and what state shapes pass through each node.

## `CostTracker`

Aggregate token usage and compute USD cost for a session.

**Signature:**

```python
@dataclass
class CostTracker:
    model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0
    prices: dict[str, tuple[float, float]] = field(
        default_factory=lambda: dict(MODEL_PRICES)
    )
```

**Usage as context manager:**

```python
from codagent.observability import CostTracker

with CostTracker(model="gpt-4o") as cost:
    # Run your agent
    result = my_agent()
    cost.record_call(input_tokens=100, output_tokens=50)

print(f"Cost: ${cost.total_usd:.4f}")
print(f"Calls: {cost.calls}")
print(f"Total tokens: {cost.total_tokens}")
```

**Methods:**

- `record_call(input_tokens=0, output_tokens=0, model=None)` — Log a single call
- `total_tokens` (property) — Sum of input and output tokens
- `total_usd` (property) — Computed cost based on model prices

**Supported models:**

The `MODEL_PRICES` table includes OpenAI and Anthropic models as of early 2026:

```python
from codagent.observability import MODEL_PRICES

# OpenAI
"gpt-4o": (0.0025, 0.010),        # (input/1k, output/1k)
"gpt-4o-mini": (0.00015, 0.0006),
"gpt-4.1": (0.005, 0.020),
"o1": (0.015, 0.060),
"o1-mini": (0.003, 0.012),

# Anthropic (approximate)
"claude-opus-4": (0.015, 0.075),
"claude-opus-4-5": (0.015, 0.075),
"claude-opus-4-7": (0.015, 0.075),
"claude-sonnet-4": (0.003, 0.015),
"claude-sonnet-4-6": (0.003, 0.015),
"claude-haiku-4": (0.0008, 0.004),
"claude-haiku-4-5": (0.0008, 0.004),
```

**Custom prices:**

```python
from codagent.observability import CostTracker, MODEL_PRICES

custom_prices = dict(MODEL_PRICES)
custom_prices["my-local-model"] = (0.0001, 0.0001)  # (input/1k, output/1k)

with CostTracker(model="my-local-model", prices=custom_prices) as cost:
    cost.record_call(input_tokens=1000, output_tokens=500)
    print(f"${cost.total_usd:.4f}")  # $0.0002
```

**Gotchas:**

- Unknown models return cost 0 silently — explicitly set `model` to enable pricing.
- Anthropic prices in the table are approximate; check the official pricing page.

---

## `StepBudget` / `StepCounter`

Guard against runaway agent loops.

### `StepBudget`

Counter that raises when it crosses a max.

**Signature:**

```python
@dataclass
class StepBudget:
    max_steps: int
    steps: int = 0
```

**Methods:**

- `step()` → `int` — Increment counter; raises `BudgetExceeded` if `steps > max_steps`
- `remaining()` → `int` — Steps left before budget is exhausted

**Example:**

```python
from codagent.observability import StepBudget, BudgetExceeded

budget = StepBudget(max_steps=5)

for i in range(10):
    try:
        step_num = budget.step()
        print(f"Step {step_num}, {budget.remaining()} remaining")
    except BudgetExceeded as e:
        print(f"Budget exceeded: {e}")
        break

# Output:
# Step 1, 4 remaining
# Step 2, 3 remaining
# Step 3, 2 remaining
# Step 4, 1 remaining
# Step 5, 0 remaining
# Budget exceeded: step budget 5 exceeded (would be step #6)
```

**In an agent loop:**

```python
from codagent.observability import StepBudget, BudgetExceeded

budget = StepBudget(max_steps=20)

while True:
    try:
        budget.step()
    except BudgetExceeded:
        print("Too many steps, stopping")
        break

    # Agent iteration
    state = graph.invoke(state)
    if state.get("done"):
        break
```

### `StepCounter`

Plain counter without a hard limit.

**Signature:**

```python
@dataclass
class StepCounter:
    count: int = 0
```

**Methods:**

- `increment()` → `int` — Increment and return count

**Example:**

```python
from codagent.observability import StepCounter

counter = StepCounter()

for i in range(5):
    num = counter.increment()
    print(f"Iteration {num}")

print(f"Total steps: {counter.count}")
```

---

## `StateTracer`

Record per-node before/after state shape and execution time.

**Signature:**

```python
class StateTracer:
    def __init__(self, *, on_step: Callable[[dict], None] | None = None):
        self.on_step = on_step  # Optional callback on each step
        self.steps: list[dict] = []  # Accumulated records
```

**Methods:**

- `wrap_node(node, name=None)` → `Callable` — Return a wrapped node that records execution
- `trace_step(name, state_before, state_after, duration_seconds, error=None)` — Manually log a step
- `to_json()` → `str` — Export steps as JSON
- `__len__()` → `int` — Number of recorded steps

**Example:**

```python
from codagent.observability import StateTracer

tracer = StateTracer()

def query_node(state):
    import time
    time.sleep(0.1)
    return {**state, "result": "done"}

wrapped = tracer.wrap_node(query_node, name="query")
wrapped({})

print(f"Recorded {len(tracer)} steps")
print(tracer.steps[0])
# {
#   'name': 'query',
#   'duration_seconds': 0.1001,
#   'before_keys': [],
#   'after_keys': ['result'],
#   'timestamp': 1704067200.123,
#   'error': None
# }

# Export for logging
json_log = tracer.to_json()
```

**With custom callback:**

```python
def on_step(record):
    # Log to external system (DataDog, Honeycomb, etc.)
    print(f"Step {record['name']} took {record['duration_seconds']}s")

tracer = StateTracer(on_step=on_step)

wrapped = tracer.wrap_node(my_node)
wrapped({})  # Calls on_step automatically
```

**In LangGraph:**

```python
from langgraph.graph import StateGraph
from codagent.observability import StateTracer

tracer = StateTracer()
graph = StateGraph(...)

graph.add_node("step1", tracer.wrap_node(step1_fn, name="step1"))
graph.add_node("step2", tracer.wrap_node(step2_fn, name="step2"))

# Run
graph.invoke({})

# Inspect
for step in tracer.steps:
    print(f"{step['name']}: {step['duration_seconds']}s, keys={step['after_keys']}")
```

**Gotchas:**

- `StateTracer` captures state keys but not values, so it's safe to use on sensitive data.
- On error, `state_after` is `None` and `error` contains the exception type name.
- Timing is wall-clock based; high-precision benchmarking should use `time.perf_counter()` instead.

---

## Combined example

```python
from codagent.observability import CostTracker, StepBudget, StateTracer

# Set up observability
cost = CostTracker(model="gpt-4o")
budget = StepBudget(max_steps=20)
tracer = StateTracer()

# Instrument your nodes
graph.add_node("step1", tracer.wrap_node(step1_fn, name="step1"))
graph.add_node("step2", tracer.wrap_node(step2_fn, name="step2"))

# Run with guards
state = {}
while not state.get("done"):
    try:
        budget.step()
    except BudgetExceeded:
        print("Runaway loop detected, stopping")
        break

    state = graph.invoke(state)
    # Manually record cost if you capture tokens
    cost.record_call(input_tokens=100, output_tokens=50)

# Report
print(f"Steps: {budget.steps}")
print(f"Cost: ${cost.total_usd:.4f}")
print(f"Traces: {len(tracer)} steps recorded")
print(tracer.to_json())
```

---

## See also

- [Nodes](nodes.md) — Stack node wrappers like `with_retry`, `with_timeout`
- [Production Hardening](../guides/production-hardening.md) — Combine all modules
