# codagent

Runtime behavior contracts for LLM agents. Forces assumption surfacing
and verification evidence at the LLM call site.

> Currently the only library that ships `AssumptionSurface` +
> `VerificationLoop` as composable runtime primitives, framework-agnostic.
> See [research](#why-this-exists) for the gap analysis.

## What it does

Wrap any LLM client (OpenAI, Anthropic, LangChain, LangGraph, raw HTTP)
with two composable contracts:

- **`AssumptionSurface`** — forces the model to lead with a labeled
  `Assumptions:` block listing decisions it would silently make. The
  user can correct course before work is wasted.
- **`VerificationLoop`** — forces the model to attach evidence (test,
  command output, visible diff) before declaring done. Bans phrases
  like "should work" / "looks correct".

Both are runtime, not training-time. Both are pure system-prompt
addenda + validators — no model fine-tuning, no DSL.

## Install

```bash
pip install codagent
```

## Quick start

```python
from openai import OpenAI
from codagent import AssumptionSurface, VerificationLoop
from codagent.adapters import wrap_openai

client = wrap_openai(
    OpenAI(),
    AssumptionSurface(min_items=2),
    VerificationLoop(),
)

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Add an export feature for users"}],
)

# Response will lead with an Assumptions: block and only declare done
# with evidence attached.
```

### LangGraph

```python
from codagent.langgraph_nodes import assumption_surface_node, verification_gate

graph.add_node("clarify", assumption_surface_node(llm=my_llm, min_items=3))
graph.add_conditional_edges(
    "execute",
    verification_gate,
    {"verified": "done", "missing": "retry"},
)
```

### Without an adapter — bring your own provider

```python
from codagent import Harness, AssumptionSurface, VerificationLoop

h = Harness(AssumptionSurface(), VerificationLoop())
wrapped = h.wrap_messages(my_messages)
# send wrapped to whatever provider you use

result = h.validate(model_response_text)
# result["all_ok"], result["AssumptionSurface"]["ok"], etc.
```

## Why this exists

A 2025-2026 ecosystem audit of LLM-agent harness libraries found three
adjacent categories — output validators (Guardrails.ai, Instructor),
observability (LangFuse, LangSmith), and conversation steering (NeMo
Guardrails / Colang) — but **no library encoded "assumption surface"
or "verification loop" as composable runtime primitives**.

This library fills that gap. The primitives derive from
[Andrej Karpathy's observations on LLM coding pitfalls](https://x.com/karpathy/status/2015883857489522876)
and the
[forrestchang/andrej-karpathy-skills](https://github.com/forrestchang/andrej-karpathy-skills)
markdown distillation, repackaged as runtime objects.

## Design principles

- **Provider-agnostic** — adapters for OpenAI, Anthropic, LangChain,
  LangGraph; manual `wrap_messages` for anything else.
- **Composable** — primitives stack via `Harness(*contracts)`.
- **No DSL** — pure Python objects, no Colang or YAML config.
- **No training** — pure system-prompt + validator. No fine-tuning,
  no model swap.
- **Honest** — `validate()` returns reasons. Don't pretend a response
  passed when it didn't.

## Status

`v0.0.1` alpha. Core API stable in spirit, may shift in shape until
`v0.1`. PRs and issue reports welcome.

## License

MIT.
