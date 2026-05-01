# Anthropic Framework Guide

Wrap an Anthropic client with codagent contracts.

## Setup

Install:

```bash
pip install codagent[anthropic]
```

## `wrap_anthropic(client, *contracts)`

Patch an Anthropic client so every `messages.create()` call appends the harness addendum to the `system` parameter.

**Signature:**

```python
def wrap_anthropic(client, *contracts) -> client:
    """Patch an Anthropic client with codagent contracts."""
```

**Arguments:**

- `client`: Anthropic client instance
- `*contracts`: Contract instances to compose into a harness

**Returns:** The same client, mutated in place.

## Basic example

```python
from anthropic import Anthropic
from codagent.harness import AssumptionSurface, VerificationLoop
from codagent.integrations import wrap_anthropic

# Create a harness with contracts
harness_contracts = [
    AssumptionSurface(min_items=2),
    VerificationLoop(),
]

# Wrap the client
client = wrap_anthropic(Anthropic(), *harness_contracts)

# Every API call now appends the harness addendum to system
response = client.messages.create(
    model="claude-opus-4-5",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Add an export feature"}],
)

print(response.content[0].text)
```

The wrapped client automatically:
1. Appends the harness addendum to the `system` parameter (if it's a string)
2. Or appends a text content block (if `system` is a list of content blocks)

## System parameter handling

Anthropic's `messages.create()` takes an optional `system` parameter (separate from `messages`). The wrapper supports both string and content-block forms:

**String system prompt:**

```python
client = wrap_anthropic(Anthropic(), AssumptionSurface())

response = client.messages.create(
    model="claude-opus-4-5",
    max_tokens=1024,
    system="You are a helpful coding assistant.",
    messages=[{"role": "user", "content": "..."}],
)
# system becomes: "You are a helpful coding assistant.\n\n[harness addendum]"
```

**Content-block system (list):**

```python
client = wrap_anthropic(Anthropic(), AssumptionSurface())

response = client.messages.create(
    model="claude-opus-4-5",
    max_tokens=1024,
    system=[
        {"type": "text", "text": "You are a helpful assistant."},
        {"type": "image", "source": {"type": "base64", "data": "..."}},
    ],
    messages=[{"role": "user", "content": "..."}],
)
# system becomes: [..., {"type": "text", "text": "[harness addendum]"}]
```

**No system parameter:**

```python
client = wrap_anthropic(Anthropic(), AssumptionSurface())

response = client.messages.create(
    model="claude-opus-4-5",
    max_tokens=1024,
    messages=[{"role": "user", "content": "..."}],
)
# system is set to just the harness addendum
```

## With cost tracking

```python
from anthropic import Anthropic
from codagent.harness import AssumptionSurface
from codagent.observability import CostTracker
from codagent.integrations import wrap_anthropic

client = wrap_anthropic(Anthropic(), AssumptionSurface())

with CostTracker(model="claude-opus-4-5") as cost:
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1024,
        messages=[{"role": "user", "content": "Summarize Python 3.13"}],
    )
    
    # Record tokens from the response
    cost.record_call(
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )

print(f"Cost: ${cost.total_usd:.4f}")
print(f"Calls: {cost.calls}")
```

## With validation

```python
from anthropic import Anthropic
from codagent.harness import Harness, AssumptionSurface, VerificationLoop
from codagent.integrations import wrap_anthropic

harness = Harness.compose(
    AssumptionSurface(min_items=2),
    VerificationLoop(),
)

client = wrap_anthropic(Anthropic(), AssumptionSurface(), VerificationLoop())

response = client.messages.create(
    model="claude-opus-4-5",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Add an export feature"}],
)

# Validate the response after the call
text = response.content[0].text
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
from anthropic import Anthropic
from codagent.nodes import with_retry, with_timeout
from codagent.harness import AssumptionSurface
from codagent.integrations import wrap_anthropic

client = wrap_anthropic(Anthropic(), AssumptionSurface())

def call_llm(state):
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1024,
        messages=state.get("messages", []),
    )
    return {"response": response.content[0].text}

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

**With tool use:**

Tool definitions are unaffected; the harness only adds system-level instructions:

```python
from anthropic import Anthropic
from codagent.harness import ToolCallSurface
from codagent.integrations import wrap_anthropic

client = wrap_anthropic(Anthropic(), ToolCallSurface())

response = client.messages.create(
    model="claude-opus-4-5",
    max_tokens=1024,
    system="You help users query the database.",
    tools=[
        {
            "name": "search",
            "description": "Search the database",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                },
                "required": ["query"],
            },
        }
    ],
    messages=[{"role": "user", "content": "Find users named Alice"}],
)

# Response now includes ToolCall: block before tool_use blocks
print(response.content)  # [TextBlock(...ToolCall:...), ToolUseBlock(...)]
```

**Streaming:**

When using streaming, the harness addendum is still injected. Collect all text chunks to validate:

```python
from anthropic import Anthropic
from codagent.harness import AssumptionSurface, Harness
from codagent.integrations import wrap_anthropic

client = wrap_anthropic(Anthropic(), AssumptionSurface())

response_text = ""
with client.messages.stream(
    model="claude-opus-4-5",
    max_tokens=1024,
    messages=[{"role": "user", "content": "..."}],
) as stream:
    for text in stream.text_stream:
        response_text += text

# Validate after streaming completes
harness = Harness.compose(AssumptionSurface())
result = harness.validate(response_text)
print(result["all_ok"])
```

---

## See also

- [Harness Module](../modules/harness.md) — Contracts and composition
- [Getting Started](../getting-started.md) — 5-minute intro
- [Production Hardening](../guides/production-hardening.md) — Full stack example
