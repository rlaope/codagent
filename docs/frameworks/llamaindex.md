# LlamaIndex Framework Guide

Wrap LlamaIndex callback handlers with codagent contracts.

## Setup

Install:

```bash
pip install codagent[llamaindex]
```

## `HarnessLlamaIndexCallback`

Returns a LlamaIndex callback handler that prepends the harness addendum to LLM events and validates outputs.

**Signature:**

```python
def HarnessLlamaIndexCallback(harness: Harness) -> BaseCallbackHandler:
    """Factory: returns a LlamaIndex BaseCallbackHandler bound to ``harness``."""
```

**Arguments:**

- `harness`: A composed `Harness`

**Returns:** A `BaseCallbackHandler` instance.

## Basic example

```python
from llama_index.core import Settings
from llama_index.core.callbacks import CallbackManager
from codagent.harness import Harness, AssumptionSurface
from codagent.integrations import HarnessLlamaIndexCallback

# Compose a harness
harness = Harness.compose(AssumptionSurface(min_items=2))

# Create the callback handler
handler = HarnessLlamaIndexCallback(harness)

# Set it globally in LlamaIndex
Settings.callback_manager = CallbackManager([handler])

# Now all LLM calls in LlamaIndex will include the harness addendum
from llama_index.core import VectorStoreIndex

# Create or load an index
index = VectorStoreIndex.from_documents([...])

# Query will automatically inject the harness
response = index.as_query_engine().query("What is Python?")
print(response)
```

## With multiple callbacks

```python
from llama_index.core import Settings
from llama_index.core.callbacks import CallbackManager, SimpleDirectoryReader
from codagent.harness import Harness, AssumptionSurface, VerificationLoop
from codagent.integrations import HarnessLlamaIndexCallback

harness = Harness.compose(
    AssumptionSurface(min_items=2),
    VerificationLoop(),
)

handler = HarnessLlamaIndexCallback(harness)

# Combine with other callbacks
Settings.callback_manager = CallbackManager([
    handler,
    # ... other handlers
])

# All LLM events now go through both handlers
from llama_index.core import VectorStoreIndex

index = VectorStoreIndex.from_documents([...])
query_engine = index.as_query_engine()
response = query_engine.query("Summarize the content")
```

## Accessing validation results

```python
from llama_index.core import Settings
from llama_index.core.callbacks import CallbackManager
from codagent.harness import Harness, AssumptionSurface
from codagent.integrations import HarnessLlamaIndexCallback

harness = Harness.compose(AssumptionSurface(min_items=2))
handler = HarnessLlamaIndexCallback(harness)

Settings.callback_manager = CallbackManager([handler])

# Make a query
from llama_index.core import VectorStoreIndex

index = VectorStoreIndex.from_documents([...])
response = index.as_query_engine().query("What is Python?")

# Check validation results from the handler
if handler.last_validation:
    result = handler.last_validation
    if result["all_ok"]:
        print("Response passed all contracts")
    else:
        for name, check in result.items():
            if name != "all_ok" and not check["ok"]:
                print(f"FAILED {name}: {check['reason']}")
```

## With chat engines

```python
from llama_index.core import Settings
from llama_index.core.callbacks import CallbackManager
from llama_index.core.chat_engine import ContextChatEngine
from codagent.harness import Harness, AssumptionSurface
from codagent.integrations import HarnessLlamaIndexCallback

harness = Harness.compose(AssumptionSurface())
handler = HarnessLlamaIndexCallback(harness)

Settings.callback_manager = CallbackManager([handler])

# Create a chat engine
from llama_index.core import VectorStoreIndex

index = VectorStoreIndex.from_documents([...])
chat_engine = index.as_chat_engine()

# Chat will include the harness
response = chat_engine.chat("What are best practices for Python?")
print(response)

# Check validation
if handler.last_validation and not handler.last_validation["all_ok"]:
    print("Response did not meet all contracts")
```

## With agents

```python
from llama_index.core import Settings
from llama_index.core.callbacks import CallbackManager
from llama_index.core.agent import AgentRunner
from codagent.harness import Harness, ToolCallSurface, AssumptionSurface
from codagent.integrations import HarnessLlamaIndexCallback

harness = Harness.compose(
    AssumptionSurface(min_items=1),
    ToolCallSurface(),
)

handler = HarnessLlamaIndexCallback(harness)
Settings.callback_manager = CallbackManager([handler])

# Create an agent with tools
from llama_index.core.tools import FunctionTool

def search_docs(query: str):
    return "search results"

tools = [FunctionTool.from_defaults(fn=search_docs)]

from llama_index.core.agent import ReActAgent

agent = ReActAgent.from_tools(tools, verbose=True)

# Agent interactions will include the harness
response = agent.chat("Find documents about Python")
print(response)

# Validation results
if handler.last_validation:
    print(handler.last_validation)
```

## With node wrappers

Combine with `codagent.nodes` wrappers for robust LLM calls:

```python
from llama_index.core import Settings
from llama_index.core.callbacks import CallbackManager
from codagent.observability import CostTracker, StateTracer
from codagent.nodes import with_retry, with_timeout
from codagent.harness import Harness, AssumptionSurface
from codagent.integrations import HarnessLlamaIndexCallback

# Set up harness and observability
harness = Harness.compose(AssumptionSurface())
handler = HarnessLlamaIndexCallback(harness)
tracer = StateTracer()

Settings.callback_manager = CallbackManager([handler])

# Wrap query execution with robustness
def query_index(state):
    index = state["index"]
    query = state["query"]
    response = index.as_query_engine().query(query)
    return {"response": str(response)}

robust_query = with_retry(
    with_timeout(query_index, seconds=30),
    attempts=3,
    on=(Exception,),
)

# Run with observability
from llama_index.core import VectorStoreIndex

index = VectorStoreIndex.from_documents([...])
result = robust_query({"index": index, "query": "What is Python?"})
print(result["response"])

# Check validation
if handler.last_validation:
    print("Validation result:", handler.last_validation["all_ok"])
```

---

## See also

- [Harness Module](../modules/harness.md) — Contracts and composition
- [Getting Started](../getting-started.md) — 5-minute intro
- [Production Hardening](../guides/production-hardening.md) — Full stack example
