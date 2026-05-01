# Getting Started

5-minute introduction to codagent. You'll wrap a node, decorate a tool, track cost, and validate a response.

## Install

```bash
pip install git+https://github.com/rlaope/codagent.git
pip install codagent[openai]  # for this guide
```

## Step 1: Wrap a node with retry

Import `with_retry` and stack it on your LLM call:

```python
from codagent.nodes import with_retry

def my_llm_call(state):
    # Simulates a network call that might fail
    import random
    if random.random() < 0.3:
        raise ConnectionError("transient failure")
    return {"result": "success"}

# Wrap with 3 attempts, 1s initial backoff, 2x exponential
robust = with_retry(
    my_llm_call,
    attempts=3,
    backoff=1.0,
    backoff_factor=2.0,
    on=(ConnectionError,),
)

# Now it retries on ConnectionError
state = robust({})
print(state)  # {'result': 'success'}
```

## Step 2: Decorate a tool with validation and rate limit

Import `validated_tool` and `rate_limit`, stack them:

```python
from codagent.tools import validated_tool, rate_limit

# Define a simple validator
def validate_search_args(kwargs):
    query = kwargs.get("query", "")
    if not query:
        raise ValueError("query required")
    limit = int(kwargs.get("limit", 10))
    if limit < 1 or limit > 100:
        raise ValueError("limit must be 1-100")
    return {"query": query, "limit": limit}

@validated_tool(validate_search_args)
@rate_limit(per_second=10)
def search_db(query: str, limit: int = 10):
    return f"searching for '{query}' (limit {limit})"

# Validation runs before the function
result = search_db(query="python agents", limit=5)
print(result)  # searching for 'python agents' (limit 5)

# Bad input raises before rate limit
try:
    search_db(query="", limit=10)
except ValueError as e:
    print(f"caught: {e}")  # caught: query required
```

## Step 3: Track token cost

Import `CostTracker` and use as a context manager:

```python
from codagent.observability import CostTracker

with CostTracker(model="gpt-4o") as cost:
    # Simulated LLM calls
    cost.record_call(input_tokens=100, output_tokens=50)
    cost.record_call(input_tokens=150, output_tokens=75)

print(f"Calls: {cost.calls}")
print(f"Total tokens: {cost.total_tokens}")
print(f"Cost: ${cost.total_usd:.4f}")
# Output:
# Calls: 2
# Total tokens: 375
# Cost: $0.0019
```

The `MODEL_PRICES` table includes OpenAI and Anthropic models. Pass custom prices:

```python
from codagent.observability import CostTracker, MODEL_PRICES

custom_prices = dict(MODEL_PRICES)
custom_prices["my-model"] = (0.001, 0.005)  # (input/1k, output/1k)

with CostTracker(model="my-model", prices=custom_prices) as cost:
    cost.record_call(input_tokens=1000, output_tokens=2000)
    print(f"${cost.total_usd:.4f}")  # $0.0110
```

## Step 4: Validate a response with a contract

Import `Harness` and a contract like `AssumptionSurface`:

```python
from codagent.harness import Harness, AssumptionSurface, VerificationLoop

# Compose a harness with contracts
harness = Harness.compose(
    AssumptionSurface(min_items=2),
    VerificationLoop(),
)

# Validate a response
response = """
Assumptions:
- User wants JSON format
- Including all historical orders

Here is the export:
[{"id": 1, "date": "2025-01-01"}]

I have verified this by running a test that confirms the export contains all orders.
"""

result = harness.validate(response)
print(result)
# {
#   'AssumptionSurface': {'ok': True, 'reason': ''},
#   'VerificationLoop': {'ok': True, 'reason': ''},
#   'all_ok': True
# }
```

A bad response fails:

```python
bad_response = "Here is your export. Done."

result = harness.validate(bad_response)
print(result)
# {
#   'AssumptionSurface': {
#     'ok': False,
#     'reason': 'no `Assumptions:` heading found'
#   },
#   'VerificationLoop': {
#     'ok': False,
#     'reason': 'unbacked claim phrase detected'
#   },
#   'all_ok': False
# }
```

## Step 5: Inject contracts into an LLM call

Import `wrap_openai` to patch an OpenAI client so every call gets the harness addendum:

```python
from openai import OpenAI
from codagent.harness import Harness, AssumptionSurface
from codagent.integrations import wrap_openai

harness = Harness.compose(AssumptionSurface(min_items=2))
client = wrap_openai(OpenAI(), AssumptionSurface(min_items=2))

# Now every messages.create call has the AssumptionSurface addendum
# injected into the system prompt automatically
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "List 3 Python libraries"}],
)
print(response.choices[0].message.content)
```

## Next steps

- [Nodes](modules/nodes.md) — Stack `with_retry`, `with_timeout`, `with_cache`, `parse_structured`
- [Tools](modules/tools.md) — Nest `validated_tool`, `circuit_breaker`, `rate_limit` decorators
- [Observability](modules/observability.md) — Guard loops with `StepBudget`, trace execution with `StateTracer`
- [Production Hardening](guides/production-hardening.md) — Combine all modules in one agent
