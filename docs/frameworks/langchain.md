# LangChain Framework Guide

Wrap LangChain Runnables and chains with codagent contracts.

## Setup

Install:

```bash
pip install codagent[langchain]
```

## `HarnessRunnable`

Wraps any LangChain Runnable so inputs are augmented with the harness addendum and outputs are validated.

**Signature:**

```python
class HarnessRunnable:
    def __init__(self, harness: Harness, inner: Runnable):
        self.harness = harness
        self._inner = inner
    
    def invoke(self, input_, config=None, **kwargs):
        ...
    
    async def ainvoke(self, input_, config=None, **kwargs):
        ...
```

**Arguments:**

- `harness`: A composed `Harness`
- `inner`: Any LangChain Runnable

**Returns:** A wrapper with `invoke()` and `ainvoke()` methods.

## Basic example

```python
from langchain_openai import ChatOpenAI
from codagent.harness import Harness, AssumptionSurface, VerificationLoop
from codagent.integrations import HarnessRunnable

# Compose a harness
harness = Harness.compose(
    AssumptionSurface(min_items=2),
    VerificationLoop(),
)

# Wrap a LangChain model
chain = HarnessRunnable(
    harness,
    ChatOpenAI(model="gpt-4o"),
)

# Invoke with a messages list
messages = [{"role": "user", "content": "Add an export feature"}]
result = chain.invoke(messages)

print(result)  # AIMessage content with Assumptions: and evidence
```

## With prompts and chains

```python
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from codagent.harness import Harness, AssumptionSurface
from codagent.integrations import HarnessRunnable

harness = Harness.compose(AssumptionSurface(min_items=2))

# Build a chain
prompt = ChatPromptTemplate.from_template(
    "You are a coding assistant. {request}"
)
model = ChatOpenAI(model="gpt-4o")
chain = prompt | model

# Wrap the chain with HarnessRunnable
harness_chain = HarnessRunnable(harness, chain)

# The harness addendum is injected before the model receives the prompt
result = harness_chain.invoke({"request": "Add pagination"})
print(result.content)
```

## With validation

```python
from langchain_openai import ChatOpenAI
from codagent.harness import Harness, AssumptionSurface, VerificationLoop
from codagent.integrations import HarnessRunnable

harness = Harness.compose(
    AssumptionSurface(min_items=2),
    VerificationLoop(),
)

chain = HarnessRunnable(
    harness,
    ChatOpenAI(model="gpt-4o"),
)

messages = [{"role": "user", "content": "Add an export feature"}]
result = chain.invoke(messages)

# Validate the response
text = result.content
validation = harness.validate(text)

if validation["all_ok"]:
    print("Response passed all contracts")
else:
    for name, check in validation.items():
        if name != "all_ok" and not check["ok"]:
            print(f"FAILED {name}: {check['reason']}")
```

## `make_harness_callback_handler`

Alternatively, use a LangChain callback handler to inject the harness into every chat-model call without wrapping the chain.

**Signature:**

```python
def make_harness_callback_handler(harness: Harness) -> BaseCallbackHandler:
    """Build a LangChain callback handler bound to this harness."""
```

**Returns:** A `BaseCallbackHandler` that injects the harness addendum into chat-model start events and validates outputs.

## Example with callback handler

```python
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from codagent.harness import Harness, AssumptionSurface
from codagent.integrations import make_harness_callback_handler

harness = Harness.compose(AssumptionSurface(min_items=2))

# Create the callback handler
handler = make_harness_callback_handler(harness)

# Build your chain normally
prompt = ChatPromptTemplate.from_template("You are a helpful assistant. {request}")
model = ChatOpenAI(model="gpt-4o")
chain = prompt | model

# Pass the handler to invoke
messages = [{"role": "user", "content": "Add pagination"}]
result = chain.invoke(
    {"request": "Add pagination"},
    config={"callbacks": [handler]},
)

print(result.content)

# Access validation result from the handler
print(handler.last_validation)
# {
#   'AssumptionSurface': {'ok': True, 'reason': ''},
#   'all_ok': True
# }
```

## With node wrappers

Stack node wrappers around a LangChain chain for robustness:

```python
from langchain_openai import ChatOpenAI
from codagent.nodes import with_retry, with_timeout
from codagent.harness import AssumptionSurface, Harness
from codagent.integrations import HarnessRunnable

harness = Harness.compose(AssumptionSurface())

chain = HarnessRunnable(
    harness,
    ChatOpenAI(model="gpt-4o"),
)

def invoke_chain(state):
    messages = state.get("messages", [])
    result = chain.invoke(messages)
    return {"response": result.content}

# Add robustness
robust_invoke = with_retry(
    with_timeout(invoke_chain, seconds=30),
    attempts=3,
    on=(ConnectionError,),
)

result = robust_invoke({"messages": [{"role": "user", "content": "..."}]})
print(result["response"])
```

## In an agent

```python
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from codagent.harness import Harness, ToolCallSurface, AssumptionSurface
from codagent.integrations import HarnessRunnable

# Compose harness
harness = Harness.compose(
    AssumptionSurface(min_items=1),
    ToolCallSurface(),
)

# Define tools
tools = [...]  # Your tools here

# Create a prompt
prompt = ChatPromptTemplate.from_template(
    "You are a helpful agent. {input}"
)

# Wrap the model with HarnessRunnable
model = HarnessRunnable(
    harness,
    ChatOpenAI(model="gpt-4o"),
)

# Create the agent
agent = create_tool_calling_agent(model, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools)

# Run the agent (harness is applied to every model call)
result = executor.invoke({"input": "Find users named Alice"})
print(result["output"])
```

---

## See also

- [Harness Module](../modules/harness.md) — Contracts and composition
- [Getting Started](../getting-started.md) — 5-minute intro
- [Production Hardening](../guides/production-hardening.md) — Full stack example
