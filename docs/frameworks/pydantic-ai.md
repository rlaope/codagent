# Pydantic AI Framework Guide

Wrap Pydantic AI agents with codagent contracts.

## Setup

Install:

```bash
pip install codagent[pydantic-ai]
```

## `pydantic_ai_prompt`

Returns a system-prompt string with the harness addendum appended.

**Signature:**

```python
def pydantic_ai_prompt(harness: Harness, *, base: str = "") -> str:
    """Return a system-prompt string with the harness addendum appended."""
```

**Arguments:**

- `harness`: A composed `Harness`
- `base`: Existing system prompt to keep above the harness rules

**Returns:** A string to pass as `system_prompt` to `Agent()`.

## Basic example

```python
from pydantic_ai import Agent
from codagent.harness import Harness, AssumptionSurface
from codagent.integrations import pydantic_ai_prompt

# Compose a harness
harness = Harness.compose(AssumptionSurface(min_items=2))

# Create the system prompt with harness addendum
system_prompt = pydantic_ai_prompt(
    harness,
    base="You are a helpful coding assistant.",
)

# Create the agent with the augmented prompt
agent = Agent(
    "openai:gpt-4o",
    system_prompt=system_prompt,
)

# Run the agent (harness rules are now active)
result = agent.run_sync("Add an export feature")
print(result.data)
```

## With validation

```python
from pydantic_ai import Agent
from pydantic import BaseModel
from codagent.harness import Harness, AssumptionSurface, VerificationLoop
from codagent.integrations import pydantic_ai_prompt

# Compose a harness
harness = Harness.compose(
    AssumptionSurface(min_items=2),
    VerificationLoop(),
)

# Create the system prompt
system_prompt = pydantic_ai_prompt(
    harness,
    base="You are a helpful assistant.",
)

# Define a response model
class Response(BaseModel):
    assumptions: str
    implementation: str
    verification: str

# Create the agent with the response model
agent = Agent(
    "openai:gpt-4o",
    system_prompt=system_prompt,
    result_type=Response,
)

# Run and validate
result = agent.run_sync("Add an export feature")
response_text = str(result.data)

# Validate against the harness
validation = harness.validate(response_text)

if validation["all_ok"]:
    print("Response passed all contracts")
else:
    for name, check in validation.items():
        if name != "all_ok" and not check["ok"]:
            print(f"FAILED {name}: {check['reason']}")
```

## With multiple contracts

```python
from pydantic_ai import Agent
from codagent.harness import Harness, AssumptionSurface, CitationRequired, VerificationLoop
from codagent.integrations import pydantic_ai_prompt

# Compose a harness with multiple contracts
harness = Harness.compose(
    AssumptionSurface(min_items=2),
    VerificationLoop(),
    CitationRequired(min_citations=1),
)

# Create the system prompt
system_prompt = pydantic_ai_prompt(
    harness,
    base="You are a research assistant. Always cite sources.",
)

# Create the agent
agent = Agent(
    "anthropic:claude-opus-4-5",
    system_prompt=system_prompt,
)

# Run the agent
result = agent.run_sync("What are the latest advances in Python?")
print(result.data)

# Validate
validation = harness.validate(result.data)
print(f"All contracts passed: {validation['all_ok']}")
```

## With dependencies

Pydantic AI agents support dependencies (tools, context, etc.). The harness only affects the system prompt, so dependencies work normally:

```python
from pydantic_ai import Agent
from pydantic_ai.tools import Tool
from codagent.harness import Harness, AssumptionSurface
from codagent.integrations import pydantic_ai_prompt

# Define tools
def search_db(query: str) -> str:
    return f"Results for {query}"

# Compose harness
harness = Harness.compose(AssumptionSurface())

# Create system prompt
system_prompt = pydantic_ai_prompt(
    harness,
    base="You are a database query assistant.",
)

# Create agent with tools
agent = Agent(
    "openai:gpt-4o",
    system_prompt=system_prompt,
    tools=[Tool(search_db, description="Search the database")],
)

# Run the agent (harness prompt + tools both active)
result = agent.run_sync("Find users named Alice")
print(result.data)
```

## With cost tracking

```python
from pydantic_ai import Agent
from codagent.harness import Harness, AssumptionSurface
from codagent.observability import CostTracker
from codagent.integrations import pydantic_ai_prompt

harness = Harness.compose(AssumptionSurface())
system_prompt = pydantic_ai_prompt(harness, base="You are helpful.")

agent = Agent(
    "openai:gpt-4o",
    system_prompt=system_prompt,
)

# Track cost manually by inspecting the response
with CostTracker(model="gpt-4o") as cost:
    result = agent.run_sync("Summarize Python 3.13")
    
    # Pydantic AI doesn't expose tokens directly, so we estimate or skip
    # Alternatively, instrument the underlying HTTP client

print(f"Cost: ${cost.total_usd:.4f}")
```

## With node wrappers

Wrap the agent call with `with_retry` and `with_timeout`:

```python
from pydantic_ai import Agent
from codagent.nodes import with_retry, with_timeout
from codagent.harness import Harness, AssumptionSurface
from codagent.integrations import pydantic_ai_prompt

harness = Harness.compose(AssumptionSurface())
system_prompt = pydantic_ai_prompt(harness, base="You are helpful.")

agent = Agent(
    "openai:gpt-4o",
    system_prompt=system_prompt,
)

def run_agent(state):
    result = agent.run_sync(state["prompt"])
    return {"response": result.data}

# Add robustness
robust_agent = with_retry(
    with_timeout(run_agent, seconds=30),
    attempts=3,
    on=(ConnectionError,),
)

result = robust_agent({"prompt": "Add an export feature"})
print(result["response"])
```

---

## See also

- [Harness Module](../modules/harness.md) — Contracts and composition
- [Getting Started](../getting-started.md) — 5-minute intro
- [Production Hardening](../guides/production-hardening.md) — Full stack example
