# codagent

[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)

**Plug-in harness system for agentic frameworks.**

`codagent` is a small library that lets you bolt **behavioral contracts**
and **domain-agent supervisors** onto LLM-based applications built on
LangChain, LangGraph, CrewAI, AutoGen, or raw OpenAI/Anthropic clients.

The harnesses themselves are pluggable — markdown rule sets, Guardrails.ai
validators, NeMo Colang flows, custom team conventions, or **meta-agents
that supervise other agents** (e.g. a finance-compliance reviewer
watching a financial-advice chatbot).

> Not a coding-agent gude. This is for people **building** agents.

## Why this exists

Most teams building agents end up writing the same kinds of behavioral
glue over and over:

- "Before calling a tool, the agent should declare why" (tool-use)
- "When the user asks for medical advice, refuse with this template"
  (conversational compliance)
- "Every factual claim in the response must carry a citation" (research)
- "A supervisor agent should review every response for SEC compliance"
  (meta-agent)

These rules already exist scattered across the OSS ecosystem (markdown
gudes, Guardrails.ai, NeMo, internal docs). `codagent` provides a thin
adapter layer so you can compose them and apply them uniformly to your
agentic framework.

## Install

```bash
pip install git+https://github.com/rlaope/codagent.git
```

Optional integrations:

```bash
pip install codagent[langchain]      # LangChain callback handler + Runnable
pip install codagent[openai]         # OpenAI client wrapper
pip install codagent[anthropic]      # Anthropic client wrapper (planned)
pip install codagent[guardrails-ai]  # wrap Guardrails.ai validators
pip install codagent[nemo]           # wrap NeMo Guardrails flows
```

## Quick start — agentic framework builder

### LangGraph customer-support agent

```python
from codagent import Harness, RefusalPattern, ToolCallSurface
from codagent.langgraph_nodes import assumption_surface_node, verification_gate

harness = Harness.compose(
    RefusalPattern(sensitive_keywords=("legal-advice", "medical-advice")),
    ToolCallSurface(),
)

graph.add_node("clarify", assumption_surface_node(my_llm))
graph.add_conditional_edges(
    "execute", verification_gate, {"verified": "done", "missing": "retry"}
)
```

### LangChain chain wrapping

```python
from langchain_openai import ChatOpenAI
from codagent import Harness, AssumptionSurface, VerificationLoop
from codagent.langchain_integration import HarnessRunnable

chain = HarnessRunnable(
    Harness.compose(AssumptionSurface(), VerificationLoop()),
    ChatOpenAI(model="gpt-4o"),
)
chain.invoke([{"role": "user", "content": "Should we refund this customer?"}])
```

### Domain agent injected as harness (meta-agent)

```python
from anthropic import Anthropic
from codagent import Harness, MetaAgentContract

claude = Anthropic()

def finance_judge(prompt: str) -> str:
    msg = claude.messages.create(
        model="claude-opus-4-5",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text

finance_supervisor = MetaAgentContract(
    name="finance-compliance",
    judge_callable=finance_judge,
    judge_prompt_template=(
        "Check whether the response includes the required disclaimer.\n\n"
        "RESPONSE: {response}\n\n"
        "Reply with COMPLIANT or NON-compliant."
    ),
    system_addendum_text=(
        "When discussing investments, always include the disclaimer "
        "'This is not financial advice.'"
    ),
)

harness = Harness.compose(finance_supervisor)
result = harness.validate(model_response_text)
# {'finance-compliance': {'ok': True/False, ...}, 'all_ok': ...}
```

## Built-in contracts

| Contract | Use for | Forces |
|---|---|---|
| `AssumptionSurface` | any agent | leading `Assumptions:` block when request is ambiguous |
| `VerificationLoop` | task-completion agents | evidence (test/output) before declaring done |
| `ToolCallSurface` | tool-use / function-calling agents | explicit `ToolCall:` block before tool invocation |
| `RefusalPattern` | conversational agents | structured `Refusal:` block for sensitive requests |
| `CitationRequired` | research / legal / medical agents | `[source: ...]` markers on factual claims |
| `MetaAgentContract` | any agent needing nuanced policy | LLM-as-judge validation by a supervisor agent |

Compose them freely:

```python
from codagent import Harness, AssumptionSurface, ToolCallSurface, RefusalPattern

domain_harness = Harness.compose(
    AssumptionSurface(min_items=2),
    ToolCallSurface(),
    RefusalPattern(sensitive_keywords=("share my password", "ssn")),
)
```

## Architecture

Three orthogonal axes:

```
Sources of harnesses     Behavior primitives    Application targets
─────────────────────    ──────────────────     ───────────────────
HarnessSource            Contract                ApplyTarget
  from_markdown            AssumptionSurface       LangChain callback
  from_guardrails_ai       VerificationLoop        LangGraph node
  from_nemo                ToolCallSurface         OpenAI wrap
  custom adapter           RefusalPattern          (file targets, bonus)
                           CitationRequired
                           MetaAgentContract
                           your custom Contract

                            \    /
                             Harness (compose, validate, apply)
```

Add your own contract: subclass `Contract`, implement `system_addendum`
and `validate`. Add your own harness source: subclass `HarnessSource`,
return contracts. PRs welcome — see [CONTRIBUTING.md](./CONTRIBUTING.md).

## Bonus: also works as a coding-agent gude installer

`codagent` also ships a CLI that writes harness rule sets into the
locations coding agents read (Claude Code, Cursor, Copilot, Codex):

```bash
codagent install \
  --from forrestchang/andrej-karpathy-skills \
  --to claude-code --to cursor --to copilot --to agents-md \
  --project ./my-app
```

This is a side feature — the main library is for agentic framework builders.

## Status

`v0.2.0` alpha. Core abstracts (Contract / HarnessSource / ApplyTarget)
are stable in spirit. Adapters and contract types continue to expand.

## License

MIT — see [LICENSE](./LICENSE). Karpathy-derived ideas attributed there.
