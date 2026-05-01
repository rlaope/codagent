# OpenAI Framework Guide

Wrap an OpenAI client with codagent contracts.

## Setup

Install:

```bash
pip install codagent[openai]
```

## `wrap_openai(client, *contracts)`

Patch an OpenAI client so every `chat.completions.create()` call injects the harness addendum into the messages array.

**Signature:**

```python
def wrap_openai(client, *contracts) -> client:
    """Patch an OpenAI client with codagent contracts."""
```

**Arguments:**

- `client`: OpenAI client instance
- `*contracts`: Contract instances to compose into a harness

**Returns:** The same client, mutated in place.

## Basic example

```python
from openai import OpenAI
from codagent.harness import AssumptionSurface, VerificationLoop
from codagent.integrations import wrap_openai

# Create a harness with contracts
harness_contracts = [
    AssumptionSurface(min_items=2),
    VerificationLoop(),
]

# Wrap the client
client = wrap_openai(OpenAI(), *harness_contracts)

# Every API call now injects the harness addendum
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Add an export feature"}],
)

print(response.choices[0].message.content)
```

The wrapped client automatically:
1. Prepends a system message with the harness addendum if none exists
2. Appends the addendum to an existing system message

## With cost tracking

```python
from openai import OpenAI
from codagent.harness import AssumptionSurface
from codagent.observability import CostTracker
from codagent.integrations import wrap_openai

client = wrap_openai(OpenAI(), AssumptionSurface())

with CostTracker(model="gpt-4o") as cost:
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Summarize Python 3.13"}],
    )
    
    # Manually record tokens from the response
    usage = response.usage
    cost.record_call(
        input_tokens=usage.prompt_tokens,
        output_tokens=usage.completion_tokens,
    )

print(f"Cost: ${cost.total_usd:.4f}")
```

## With validation

```python
from openai import OpenAI
from codagent.harness import Harness, AssumptionSurface, VerificationLoop
from codagent.integrations import wrap_openai

harness = Harness.compose(
    AssumptionSurface(min_items=2),
    VerificationLoop(),
)

client = wrap_openai(OpenAI(), AssumptionSurface(), VerificationLoop())

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Add an export feature"}],
)

# Validate the response after the call
text = response.choices[0].message.content
result = harness.validate(text)

if result["all_ok"]:
    print("Response passed all contracts")
else:
    for name, check in result.items():
        if name != "all_ok" and not check["ok"]:
            print(f"FAILED {name}: {check['reason']}")
```

## With node wrappers

Stack node wrappers around the LLM call for production robustness:

```python
from openai import OpenAI
from codagent.nodes import with_retry, with_timeout
from codagent.harness import AssumptionSurface
from codagent.integrations import wrap_openai

client = wrap_openai(OpenAI(), AssumptionSurface())

def call_llm(state):
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=state.get("messages", []),
    )
    return {"response": response.choices[0].message.content}

# Add robustness
robust_call = with_retry(
    with_timeout(call_llm, seconds=30),
    attempts=3,
    backoff=1.0,
    on=(ConnectionError, TimeoutError),
)

result = robust_call({"messages": [{"role": "user", "content": "..."}]})
print(result["response"])
```

## Common patterns

**Streaming:**

When using streaming, the harness addendum is still injected, but you must validate the complete response after collecting all chunks:

```python
client = wrap_openai(OpenAI(), AssumptionSurface())

response_text = ""
with client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "..."}],
    stream=True,
) as stream:
    for chunk in stream:
        if chunk.choices[0].delta.content:
            response_text += chunk.choices[0].delta.content

# Validate after streaming completes
harness = Harness.compose(AssumptionSurface())
result = harness.validate(response_text)
print(result["all_ok"])
```

**With tool calling:**

Tool definitions are unaffected by the harness; it only adds system-level instructions:

```python
import json
from openai import OpenAI
from codagent.harness import ToolCallSurface
from codagent.integrations import wrap_openai

client = wrap_openai(OpenAI(), ToolCallSurface())

tools = [
    {
        "type": "function",
        "function": {
            "name": "search_db",
            "description": "Search the database",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                },
                "required": ["query"],
            },
        },
    }
]

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Find users named Alice"}],
    tools=tools,
)

# The response now includes a ToolCall: block in its text before tool_calls
print(response.choices[0].message.content)  # ToolCall: ...
print(response.choices[0].message.tool_calls)  # [...]
```

---

## See also

- [Harness Module](../modules/harness.md) — Contracts and composition
- [Getting Started](../getting-started.md) — 5-minute intro
- [Production Hardening](../guides/production-hardening.md) — Full stack example
