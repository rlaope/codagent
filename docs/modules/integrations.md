# Integrations

Framework-specific adapters: nine working integrations plus stubs for emerging frameworks.

## Overview

The core codagent library is framework-agnostic. Integrations plug harnesses and utilities into specific LLM frameworks via adapters. Install only what your stack needs:

```bash
pip install codagent[openai]         # OpenAI client wrap
pip install codagent[anthropic]      # Anthropic client wrap
pip install codagent[langchain]      # LangChain callback + Runnable
pip install codagent[langgraph]      # LangGraph node factories
pip install codagent[llamaindex]     # LlamaIndex callback handler
pip install codagent[pydantic-ai]    # Pydantic AI system-prompt helper
pip install codagent[crewai]         # CrewAI agent backstory adapter
pip install codagent[autogen]        # AutoGen system-message adapter
pip install codagent[dspy]           # DSPy module wrapper
pip install codagent[guardrails-ai]  # wrap Guardrails.ai validators
pip install codagent[nemo]           # wrap NeMo Guardrails flows
```

## Working integrations

### OpenAI

**`wrap_openai(client, *contracts)`** — Patch an OpenAI client so every `messages.create()` call injects the harness addendum.

Works with: OpenAI Python SDK >= 1.0 (chat completions API).

See [OpenAI Framework Guide](../frameworks/openai.md) for full details and examples.

### Anthropic

**`wrap_anthropic(client, *contracts)`** — Patch an Anthropic client so every `messages.create()` call appends the harness addendum to the `system` parameter.

Works with: Anthropic Python SDK >= 0.30 (messages API).

See [Anthropic Framework Guide](../frameworks/anthropic.md) for full details and examples.

### LangChain

**`HarnessRunnable(harness, inner_runnable)`** — Wraps any LangChain Runnable so inputs are augmented with the harness addendum and outputs are validated.

**`make_harness_callback_handler(harness)`** — Returns a LangChain `BaseCallbackHandler` that injects the harness addendum into chat-model prompts and validates outputs.

Works with: LangChain >= 0.1 (Runnable interface), LangChain Core >= 0.1 (callbacks).

See [LangChain Framework Guide](../frameworks/langchain.md) for full details and examples.

### LangGraph

**`assumption_surface_node(llm, min_items=1)`** — Returns a LangGraph node callable that asks the LLM for assumptions.

**`verification_gate(state, evidence_field="evidence")`** — Conditional-edge function that returns `"verified"` or `"missing"` based on whether the state contains evidence.

Works with: LangGraph >= 0.1.

See [LangGraph Framework Guide](../frameworks/langgraph.md) for full details and examples.

### Pydantic AI

**`pydantic_ai_prompt(harness, base="")`** — Returns a system-prompt string with the harness addendum appended.

Works with: Pydantic AI >= 0.1.

See [Pydantic AI Framework Guide](../frameworks/pydantic-ai.md) for full details and examples.

### LlamaIndex

**`HarnessLlamaIndexCallback(harness)`** — Returns a LlamaIndex `BaseCallbackHandler` that prepends the harness addendum to LLM events.

Works with: LlamaIndex >= 0.9 (callbacks API).

See [LlamaIndex Framework Guide](../frameworks/llamaindex.md) for full details and examples.

## Stub integrations

The following are placeholder adapters. Contributions welcome.

### CrewAI

Planned: `crewai` integration to inject harness into agent backstory.

### AutoGen

Planned: `autogen` integration to inject harness into system messages.

### DSPy

Planned: `dspy` integration to wrap DSPy modules with harness validation.

## Import paths

All integrations are exported from `codagent.integrations`:

```python
from codagent.integrations import (
    wrap_openai,
    wrap_anthropic,
    pydantic_ai_prompt,
    HarnessRunnable,
    make_harness_callback_handler,
    assumption_surface_node,
    verification_gate,
    HarnessLlamaIndexCallback,
)
```

Some are also re-exported from submodules for backwards compatibility:

```python
# These both work
from codagent.integrations import wrap_openai
from codagent.harness.targets import wrap_openai

from codagent.integrations import HarnessRunnable
from codagent.harness.langchain_integration import HarnessRunnable
```

---

## See also

- [OpenAI Framework Guide](../frameworks/openai.md)
- [Anthropic Framework Guide](../frameworks/anthropic.md)
- [LangChain Framework Guide](../frameworks/langchain.md)
- [LangGraph Framework Guide](../frameworks/langgraph.md)
- [Pydantic AI Framework Guide](../frameworks/pydantic-ai.md)
- [LlamaIndex Framework Guide](../frameworks/llamaindex.md)
