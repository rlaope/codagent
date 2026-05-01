# Harness

Behavior contracts and composer. Build via `Harness.compose(...)` mixing contracts, apply to OpenAI clients, LangChain Runnables, LangGraph nodes, or output files.

## Overview

The harness is a bundle of behavioral contracts that inject validation logic into LLM calls. Each contract forces the model to surface certain outputs (assumptions, evidence, tool intent, etc.) and provides a validator to check compliance.

## `Harness` composer

Build a harness by composing contracts:

**Signature:**

```python
class Harness:
    @classmethod
    def compose(cls, *items) -> "Harness": ...
    
    def system_addendum(self) -> str: ...
    def wrap_messages(self, messages: list[dict]) -> list[dict]: ...
    def validate(self, response: str) -> dict: ...
    def apply(self, target: ApplyTarget) -> None: ...
```

**Methods:**

- `compose(*items)` — Mix `HarnessSource` instances and `Contract` instances into one harness
- `system_addendum()` → `str` — Get the combined system prompt injection
- `wrap_messages(messages)` → `list[dict]` — Inject harness into a messages array
- `validate(response)` → `dict` — Check a response against all contracts
- `apply(target)` — Write harness to a runtime (OpenAI client, LangGraph, etc.)

**Example:**

```python
from codagent.harness import Harness, AssumptionSurface, VerificationLoop, CitationRequired

harness = Harness.compose(
    AssumptionSurface(min_items=2),
    VerificationLoop(),
    CitationRequired(min_citations=1),
)

# Get the system addendum
addendum = harness.system_addendum()
print(addendum)
# When the user's request leaves any decision unspecified...
# Before declaring any task done...
# Every factual claim...

# Wrap messages for an API call
messages = [{"role": "user", "content": "What's the capital of France?"}]
wrapped = harness.wrap_messages(messages)
# wrapped[0] is now a system message with the addendum

# Validate a response
response = """
Assumptions:
- Asking about the French capital city
- Modern era (current day)

The capital of France is Paris [source: wikipedia]. 
I verified this by checking multiple sources.
"""

result = harness.validate(response)
print(result)
# {
#   'AssumptionSurface': {'ok': True, 'reason': ''},
#   'VerificationLoop': {'ok': True, 'reason': ''},
#   'CitationRequired': {'ok': True, 'reason': ''},
#   'all_ok': True
# }
```

---

## Built-in contracts

### `AssumptionSurface`

Force the agent to surface its assumptions before acting.

**Signature:**

```python
@dataclass
class AssumptionSurface(Contract):
    min_items: int = 1
    name: str = "AssumptionSurface"
```

**What it forces:** Agent must prepend an `Assumptions:` block listing decisions when the request is ambiguous (scope, format, scale, edge cases, target audience).

**Validation:** Checks for `Assumptions:` heading and at least `min_items` bullet points.

**Example:**

```python
from codagent.harness import AssumptionSurface

contract = AssumptionSurface(min_items=2)
print(contract.system_addendum())
# When the user's request leaves any decision unspecified (scope, format, 
# scale, edge cases, target audience), prepend your response with an 
# `Assumptions:` block listing the decisions you're making...

# Valid response
response = """
Assumptions:
- User wants active customers only (excluding churn)
- JSON format with all fields

Here is the customer list:
[{"id": 1, "name": "Acme"}]
"""

ok, reason = contract.validate(response)
print(ok)  # True

# Invalid: missing assumptions
response2 = "Here are your customers..."
ok, reason = contract.validate(response2)
print(ok, reason)  # False, "no `Assumptions:` heading found"
```

---

### `VerificationLoop`

Force the agent to back any "done" claim with evidence.

**Signature:**

```python
@dataclass
class VerificationLoop(Contract):
    name: str = "VerificationLoop"
```

**What it forces:** Before declaring a task done, complete, fixed, or ready, the agent must produce one of:
- A passing test it wrote
- A command output showing the new behavior
- A diff that visibly satisfies the success criteria
- Or an honest "I have not verified this" statement

**Validation:** Checks for evidence markers (`test passed`, `exit code 0`, `output:`, etc.) or explicit "not verified" statement. Rejects unbacked phrases like "should work" or "looks correct".

**Example:**

```python
from codagent.harness import VerificationLoop

contract = VerificationLoop()

# Valid: has evidence
response = """
I've added the export feature. The tests pass:

$ pytest test_export.py -v
test_export.py::test_export_csv PASSED

All tests passed.
"""

ok, reason = contract.validate(response)
print(ok)  # True

# Invalid: unbacked claim
response2 = "I've added the feature. It should work."
ok, reason = contract.validate(response2)
print(ok, reason)  # False, "unbacked claim phrase detected"
```

---

### `ToolCallSurface`

Force the agent to declare tool intent before invoking.

**Signature:**

```python
@dataclass
class ToolCallSurface(Contract):
    name: str = "ToolCallSurface"
```

**What it forces:** Before invoking any tool, prepend a `ToolCall:` block stating:
- which tool you are about to call
- why this tool, not another
- what you expect to learn or change

**Validation:** If the response mentions executing a tool, a `ToolCall:` block must appear.

**Example:**

```python
from codagent.harness import ToolCallSurface

contract = ToolCallSurface()

# Valid: has ToolCall block
response = """
ToolCall:
  tool: search_orders
  why: user mentioned 'last order' but no ID; need to find theirs
  expect: 0-3 recent orders for this customer

Let me find your most recent order...
[calling search_orders]
"""

ok, reason = contract.validate(response)
print(ok)  # True
```

---

### `RefusalPattern`

Force explicit refusal blocks for sensitive request categories.

**Signature:**

```python
@dataclass
class RefusalPattern(Contract):
    sensitive_keywords: tuple[str, ...] = field(default_factory=tuple)
    name: str = "RefusalPattern"
```

**What it forces:** If the request touches any `sensitive_keywords`, respond with a `Refusal:` block stating:
- the policy or principle you are invoking
- what alternative action the user can take

**Validation:** If sensitive keywords are present, a `Refusal:` block must appear.

**Example:**

```python
from codagent.harness import RefusalPattern

contract = RefusalPattern(
    sensitive_keywords=("credit card", "ssn", "password", "api key")
)

# Valid: explicit refusal
response = """
Refusal:
  policy: I cannot handle financial data like credit cards
  alternative: Use our PCI-compliant checkout or contact support@example.com

I'd be happy to help with other features.
"""

ok, reason = contract.validate(response)
print(ok)  # True

# Invalid: partial compliance
response2 = "I can't help with that, sorry."
ok, reason = contract.validate(response2)
print(ok, reason)  # False, "sensitive keyword(s) present... but no `Refusal:` block"
```

---

### `CitationRequired`

Force every factual claim to carry a `[source: ...]` marker.

**Signature:**

```python
@dataclass
class CitationRequired(Contract):
    min_citations: int = 1
    name: str = "CitationRequired"
```

**What it forces:** Every factual claim must be followed by `[source: <name or URL or 'not verified'>]`. Opinions and reasoning steps don't need citations.

**Validation:** Counts `[source: ...]` markers. Honest "not verified" is acceptable.

**Example:**

```python
from codagent.harness import CitationRequired

contract = CitationRequired(min_citations=1)

# Valid: citations present
response = """
Python is the most popular language for AI [source: Stack Overflow survey 2024].
The Python ecosystem has 500k+ packages [source: PyPI, not verified].
"""

ok, reason = contract.validate(response)
print(ok)  # True

# Invalid: no citations
response2 = "Python is very popular. AI is growing."
ok, reason = contract.validate(response2)
print(ok, reason)  # False, "found 0 citation markers, need at least 1"
```

---

### `MetaAgentContract`

A contract whose `validate()` runs an LLM as judge.

**Signature:**

```python
class MetaAgentContract(Contract):
    def __init__(
        self,
        name: str,
        judge_callable: Callable[[str], str],
        judge_prompt_template: str,
        compliance_marker: str = "COMPLIANT",
        system_addendum_text: str = "",
    ):
        self.name = name
        self._judge = judge_callable
        self._template = judge_prompt_template
        self._marker = compliance_marker
        self._addendum = system_addendum_text
```

**What it forces:** When `validate()` is called, the judge LLM is asked to evaluate the response for compliance with a domain rule. The judge must return text containing the `compliance_marker` to pass.

**Use when:** The rule is too nuanced for regex — e.g., "did the response give investment advice without proper disclaimers?", "is the medical answer peer-reviewed?", "does the customer service reply match our tone guidelines?"

**Example (finance domain):**

```python
from codagent.harness import MetaAgentContract
from anthropic import Anthropic

def judge_call(prompt: str) -> str:
    client = Anthropic()
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text

contract = MetaAgentContract(
    name="InvestmentDisclaimer",
    judge_callable=judge_call,
    judge_prompt_template=(
        "Does this response give investment advice without proper disclaimers? "
        "Response:\n{response}\n\n"
        "Answer with '{marker}' if the response is compliant, 'NON-COMPLIANT' otherwise."
    ),
    compliance_marker="COMPLIANT",
    system_addendum_text="Never give financial advice without a disclaimer.",
)

response = "You should buy Apple stock. Disclaimer: this is not investment advice."
ok, reason = contract.validate(response)
print(ok)  # True (judge finds the disclaimer)
```

**Example (medical domain):**

```python
from codagent.harness import MetaAgentContract
from anthropic import Anthropic

def judge_call(prompt: str) -> str:
    client = Anthropic()
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text

contract = MetaAgentContract(
    name="MedicalAccuracy",
    judge_callable=judge_call,
    judge_prompt_template=(
        "Is this medical advice based on peer-reviewed evidence? "
        "Response:\n{response}\n\n"
        "Answer with '{marker}' if evidence-based, 'NOT-VERIFIED' if not."
    ),
    compliance_marker="VERIFIED",
    system_addendum_text="All medical claims must cite peer-reviewed research.",
)

response = "Aspirin helps reduce heart attack risk [source: AHA 2023 guidelines]."
ok, reason = contract.validate(response)
```

---

## Composing and applying

**Mix contracts:**

```python
from codagent.harness import Harness, AssumptionSurface, VerificationLoop, CitationRequired

harness = Harness.compose(
    AssumptionSurface(min_items=2),
    VerificationLoop(),
    CitationRequired(min_citations=1),
)
```

**Validate output:**

```python
response = """
Assumptions:
- Query is for active customers only
- JSON format preferred

The customer data is:
[...]

I verified by running the query against production [source: internal logs].
"""

result = harness.validate(response)
if result["all_ok"]:
    print("Passed all contracts")
else:
    for contract_name, check in result.items():
        if contract_name != "all_ok" and not check["ok"]:
            print(f"{contract_name}: {check['reason']}")
```

**Apply to OpenAI client:**

```python
from openai import OpenAI
from codagent.integrations import wrap_openai

harness = Harness.compose(AssumptionSurface(), VerificationLoop())
client = wrap_openai(OpenAI(), AssumptionSurface(), VerificationLoop())

# Every call now injects the harness addendum
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "..."}],
)
```

---

## See also

- [Anthropic Framework Guide](../frameworks/anthropic.md)
- [OpenAI Framework Guide](../frameworks/openai.md)
- [LangChain Framework Guide](../frameworks/langchain.md)
- [LangGraph Framework Guide](../frameworks/langgraph.md)
- [Behavior Contracts Guide](../guides/behavior-contracts.md)
- [Meta-Agent Supervisor Guide](../guides/meta-agent-supervisor.md)
