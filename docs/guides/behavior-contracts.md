# Behavior Contracts

Deep dive on harness contracts: when to use which, composing custom contracts.

## Contract types

Codagent includes six built-in contracts covering major agent behavior categories.

### General reasoning (Karpathy core)

**`AssumptionSurface`** — Force the agent to surface its assumptions when the request is ambiguous.

Use when:
- User request leaves decisions unspecified (scope, format, scale, edge cases)
- You want the model to ask clarifying questions before acting
- Preventing silent assumptions that could be wrong

Example:
```python
from codagent.harness import Harness, AssumptionSurface

harness = Harness.compose(AssumptionSurface(min_items=2))
response = """
Assumptions:
- User wants all active customers, not soft-deleted
- JSON format with all fields

Here are the customers:
[...]
"""
result = harness.validate(response)
print(result["AssumptionSurface"]["ok"])  # True
```

---

**`VerificationLoop`** — Force the agent to back any "done" claim with evidence.

Use when:
- Agent claims a task is complete, fixed, or ready
- You require proof: a test, command output, or diff
- You want to prevent unbacked claims like "should work" or "looks correct"

Example:
```python
from codagent.harness import Harness, VerificationLoop

harness = Harness.compose(VerificationLoop())
response = """
I've fixed the bug. The tests pass:

$ pytest test_bug.py -v
test_bug.py::test_fix PASSED

All tests passed.
"""
result = harness.validate(response)
print(result["VerificationLoop"]["ok"])  # True
```

### Tool-use (agentic systems)

**`ToolCallSurface`** — Force the agent to declare tool intent before invoking.

Use when:
- Agent uses tools or function calling
- You want to prevent silent tool spam
- You want to understand why a tool is being called before it runs

Example:
```python
from codagent.harness import Harness, ToolCallSurface

harness = Harness.compose(ToolCallSurface())
response = """
ToolCall:
  tool: search_orders
  why: user mentioned 'last order' but no ID; need to find theirs
  expect: 0-3 recent orders for this customer

Calling the search tool...
"""
result = harness.validate(response)
print(result["ToolCallSurface"]["ok"])  # True
```

### Conversational / domain compliance

**`RefusalPattern`** — Force explicit refusal blocks for sensitive request categories.

Use when:
- Requests may touch sensitive keywords (credit card, SSN, password, API key)
- You want explicit refusals that downstream code can branch on
- You need clear audit trails for compliance

Example:
```python
from codagent.harness import Harness, RefusalPattern

harness = Harness.compose(
    RefusalPattern(sensitive_keywords=("credit card", "ssn", "password"))
)

response = """
Refusal:
  policy: I cannot handle financial data
  alternative: Use our PCI-compliant checkout

I'd be happy to help with other things.
"""
result = harness.validate(response)
print(result["RefusalPattern"]["ok"])  # True
```

---

**`CitationRequired`** — Force every factual claim to carry a `[source: ...]` marker.

Use when:
- Agent makes factual claims that must be sourced
- You work in research, legal, medical, or compliance domains
- Unsourced claims are unacceptable
- Honest "not verified" is better than missing source

Example:
```python
from codagent.harness import Harness, CitationRequired

harness = Harness.compose(CitationRequired(min_citations=1))

response = """
Python is the most popular language for AI [source: Stack Overflow 2024].
It has 500k+ packages [source: PyPI stats].
Not all of this is actively maintained [source: not verified].
"""
result = harness.validate(response)
print(result["CitationRequired"]["ok"])  # True
```

### Meta-agent (domain agent injected as harness)

**`MetaAgentContract`** — A contract whose `validate()` runs an LLM as judge.

Use when:
- The rule is too nuanced for regex
- You need domain expertise to validate
- Examples: "did the response give investment advice without disclaimers?", "is the answer medically accurate?", "does it respect tone-of-voice?"

Example:
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
        "Does this give investment advice without proper disclaimers? "
        "Response:\n{response}\n\n"
        "Answer with '{marker}' if compliant, 'NOT-COMPLIANT' otherwise."
    ),
    compliance_marker="COMPLIANT",
    system_addendum_text="Never give financial advice without a disclaimer.",
)

response = "You should buy Apple stock. Disclaimer: this is not investment advice."
ok, reason = contract.validate(response)
print(ok)  # True (judge found the disclaimer)
```

---

## Composing contracts

Mix contracts freely:

```python
from codagent.harness import Harness, AssumptionSurface, VerificationLoop, CitationRequired

harness = Harness.compose(
    AssumptionSurface(min_items=2),
    VerificationLoop(),
    CitationRequired(min_citations=1),
)

# All three contracts are now active
result = harness.validate(response)
print(result["all_ok"])  # True only if all pass
```

The order of composition doesn't matter for validation (all are checked). But system-prompt injection happens in order.

## Writing custom contracts

Subclass `Contract`:

```python
from codagent.harness import Contract

class MyCustomContract(Contract):
    name: str = "MyCustom"
    
    def system_addendum(self) -> str:
        """Return text injected into the system prompt."""
        return (
            "You must include a '## Summary' section at the end "
            "of every response."
        )
    
    def validate(self, response: str) -> tuple[bool, str]:
        """Return (ok, reason)."""
        if "## Summary" not in response:
            return False, "missing '## Summary' section"
        return True, ""
```

Use it:

```python
from codagent.harness import Harness

harness = Harness.compose(MyCustomContract())
```

### Example: word count contract

```python
from codagent.harness import Contract

class WordCount(Contract):
    def __init__(self, min_words: int, max_words: int):
        self.min_words = min_words
        self.max_words = max_words
        self.name = f"WordCount({min_words}-{max_words})"
    
    def system_addendum(self) -> str:
        return (
            f"Your response must be between {self.min_words} "
            f"and {self.max_words} words."
        )
    
    def validate(self, response: str) -> tuple[bool, str]:
        words = len(response.split())
        if words < self.min_words:
            return False, f"only {words} words, need at least {self.min_words}"
        if words > self.max_words:
            return False, f"{words} words, limit is {self.max_words}"
        return True, ""
```

Use it:

```python
from codagent.harness import Harness

harness = Harness.compose(
    WordCount(min_words=100, max_words=500),
)

response = "Short answer."
ok, reason = harness.validate(response)
print(ok, reason)  # False, "only 2 words, need at least 100"
```

### Example: structured output contract

```python
from codagent.harness import Contract
import json

class StructuredJSON(Contract):
    def __init__(self, required_fields: list[str]):
        self.required_fields = required_fields
        self.name = f"StructuredJSON({', '.join(required_fields)})"
    
    def system_addendum(self) -> str:
        fields_str = ", ".join(self.required_fields)
        return (
            f"You must respond with valid JSON containing these fields: "
            f"{fields_str}"
        )
    
    def validate(self, response: str) -> tuple[bool, str]:
        try:
            data = json.loads(response)
            missing = [f for f in self.required_fields if f not in data]
            if missing:
                return False, f"missing fields: {missing}"
            return True, ""
        except json.JSONDecodeError as e:
            return False, f"invalid JSON: {e}"
```

Use it:

```python
from codagent.harness import Harness

harness = Harness.compose(
    StructuredJSON(required_fields=["action", "reason", "result"]),
)

response = '{"action": "delete", "reason": "spam", "result": "success"}'
ok, reason = harness.validate(response)
print(ok)  # True
```

---

## Testing contracts

Test contracts independently:

```python
from codagent.harness import Contract

contract = MyCustomContract()

# Test system addendum
addendum = contract.system_addendum()
assert "Summary" in addendum

# Test validation
response1 = "Some text.\n## Summary\nHere's a summary."
ok1, msg1 = contract.validate(response1)
assert ok1

response2 = "Some text without summary."
ok2, msg2 = contract.validate(response2)
assert not ok2
assert "missing" in msg2
```

---

## See also

- [Harness Module](../modules/harness.md)
- [Meta-Agent Supervisor Guide](meta-agent-supervisor.md)
- [Production Hardening Guide](production-hardening.md)
