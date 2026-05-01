# Meta-Agent Supervisor

Use `MetaAgentContract` for domain compliance via LLM-as-judge.

## Overview

A meta-agent contract delegates validation to another LLM (the "judge"). This is useful when the rule is too nuanced for regex and requires domain expertise: financial compliance, medical accuracy, legal review, tone-of-voice matching, etc.

## Architecture

1. Main agent generates a response
2. Judge LLM evaluates the response against a domain rule
3. Judge returns a judgment string containing a compliance marker
4. `MetaAgentContract.validate()` checks for the marker

```
User Request
    ↓
Main Agent (with harness system prompt)
    ↓
Response Text
    ↓
Judge LLM (evaluates against domain rule)
    ↓
Judgment (contains "COMPLIANT" or "NOT COMPLIANT")
    ↓
MetaAgentContract.validate()
    ↓
(ok: bool, reason: str)
```

## Finance domain example

Force investment disclaimers:

```python
from codagent.harness import MetaAgentContract, Harness
from anthropic import Anthropic

def judge_call(prompt: str) -> str:
    """Call the judge LLM."""
    client = Anthropic()
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text

# Create the meta-agent contract
contract = MetaAgentContract(
    name="InvestmentDisclaimer",
    judge_callable=judge_call,
    judge_prompt_template=(
        "You are a financial compliance reviewer.\n\n"
        "Does this response give investment advice without proper disclaimers?\n\n"
        "Response to review:\n{response}\n\n"
        "Rules:\n"
        "- Any recommendation to buy/sell must include a disclaimer\n"
        "- Past performance is not a guarantee of future results\n"
        "- Diversification is not a guarantee of profit or protection\n\n"
        "Respond with '{marker}' if the response is compliant, "
        "or 'NON-COMPLIANT: [reason]' if not."
    ),
    compliance_marker="COMPLIANT",
    system_addendum_text=(
        "You are a financial advisor. "
        "When giving investment advice, always include appropriate disclaimers."
    ),
)

# Test it
harness = Harness.compose(contract)

# Compliant response
compliant = """
I recommend diversifying across stocks and bonds.

Disclaimer: This is not investment advice. Past performance does not guarantee 
future results. Diversification does not guarantee profit or protect against loss.
Consult a licensed financial advisor before making investment decisions.
"""

ok, msg = contract.validate(compliant)
print(f"Compliant: {ok}")  # True

# Non-compliant response
non_compliant = """
You should definitely buy Apple stock right now. It's going to the moon.
"""

ok, msg = contract.validate(non_compliant)
print(f"Non-compliant: {ok}, Reason: {msg}")  # False, reason from judge
```

## Healthcare domain example

Force evidence-based medical claims:

```python
from codagent.harness import MetaAgentContract, Harness
from anthropic import Anthropic

def judge_call(prompt: str) -> str:
    client = Anthropic()
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text

contract = MetaAgentContract(
    name="MedicalAccuracy",
    judge_callable=judge_call,
    judge_prompt_template=(
        "You are a medical evidence reviewer.\n\n"
        "Is this medical response based on current peer-reviewed evidence?\n\n"
        "Response to review:\n{response}\n\n"
        "Standards:\n"
        "- Treatment recommendations must cite peer-reviewed studies\n"
        "- Diagnostic claims must be evidence-based\n"
        "- Unproven treatments must be labeled as such\n"
        "- Patient should be advised to consult a licensed physician\n\n"
        "Respond with '{marker}' if evidence-based and appropriate, "
        "or 'NOT-VERIFIED: [reason]' if not."
    ),
    compliance_marker="VERIFIED",
    system_addendum_text=(
        "You are a medical information assistant. "
        "All medical claims must be based on peer-reviewed evidence. "
        "Always advise users to consult a licensed physician."
    ),
)

harness = Harness.compose(contract)

# Compliant response
good = """
For mild anxiety, cognitive behavioral therapy (CBT) is recommended by the 
American Psychiatric Association and has strong evidence support 
[source: APA 2023 guidelines].

Medication options include SSRIs, which are first-line treatments 
[source: Lancet 2022 systematic review].

Please consult a licensed physician for a proper diagnosis and treatment plan.
"""

ok, msg = contract.validate(good)
print(f"Good: {ok}")  # True

# Non-compliant response
bad = """
Just take this supplement I found online. It cures anxiety without any side effects.
"""

ok, msg = contract.validate(bad)
print(f"Bad: {ok}")  # False, with reason from judge
```

## Legal domain example

Force proper citation and disclaimers:

```python
from codagent.harness import MetaAgentContract, Harness
from anthropic import Anthropic

def judge_call(prompt: str) -> str:
    client = Anthropic()
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text

contract = MetaAgentContract(
    name="LegalCompliance",
    judge_callable=judge_call,
    judge_prompt_template=(
        "You are a legal compliance reviewer.\n\n"
        "Does this legal response meet professional standards?\n\n"
        "Response to review:\n{response}\n\n"
        "Requirements:\n"
        "- Any legal conclusion must cite applicable law\n"
        "- Must include attorney-client privilege notice\n"
        "- Must not constitute legal advice\n"
        "- Must recommend consulting an attorney\n\n"
        "Respond with '{marker}' if compliant with all requirements, "
        "or 'NOT-COMPLIANT: [reason]' if not."
    ),
    compliance_marker="COMPLIANT",
    system_addendum_text=(
        "You are a legal information system. "
        "Include: attorney-client privilege notice, citation of applicable law, "
        "disclaimer that this is not legal advice, recommendation to consult counsel."
    ),
)

harness = Harness.compose(contract)

# Compliant response
good = """
Under 42 U.S.C. § 1983, civil rights actions against state actors require 
action under color of state law.

IMPORTANT NOTICE: This is not legal advice. Attorney-client privilege does not 
apply to this response. You must consult a licensed attorney for legal advice 
regarding your specific situation.
"""

ok, msg = contract.validate(good)
print(f"Good: {ok}")  # True
```

## Customer service domain example

Force tone-of-voice compliance:

```python
from codagent.harness import MetaAgentContract, Harness
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
    name="ToneOfVoice",
    judge_callable=judge_call,
    judge_prompt_template=(
        "You are a brand voice reviewer for a luxury hotel.\n\n"
        "Does this customer service response match our tone-of-voice guidelines?\n\n"
        "Response:\n{response}\n\n"
        "Brand voice guidelines:\n"
        "- Warm, professional, and elegant\n"
        "- Empathetic to guest concerns\n"
        "- Solution-focused\n"
        "- Never dismissive or robotic\n\n"
        "Respond with '{marker}' if it matches our brand voice, "
        "or 'OFF-BRAND: [reason]' if not."
    ),
    compliance_marker="MATCHES",
    system_addendum_text=(
        "You are a luxury hotel concierge. "
        "Be warm, professional, and empathetic. "
        "Always offer solutions, not excuses."
    ),
)

harness = Harness.compose(contract)

# Compliant
good = """
I'm genuinely sorry to hear about the issue with your room. 
We take pride in your experience, and I'd like to make this right immediately.

Let me arrange a room change to one of our premium suites at no additional charge 
and have our housekeeping team personally ensure it's perfect for you.

How does that sound?
"""

ok, msg = contract.validate(good)
print(f"Good: {ok}")  # True

# Non-compliant
bad = """
Room issues happen. Try clearing the cache or restarting.
"""

ok, msg = contract.validate(bad)
print(f"Bad: {ok}")  # False
```

## Integration patterns

### With framework adapters

```python
from openai import OpenAI
from codagent.harness import Harness, MetaAgentContract
from codagent.integrations import wrap_openai
from anthropic import Anthropic

def judge_call(prompt):
    return Anthropic().messages.create(
        model="claude-opus-4-5",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    ).content[0].text

contract = MetaAgentContract(
    name="MyDomain",
    judge_callable=judge_call,
    judge_prompt_template="...",
    compliance_marker="APPROVED",
)

harness = Harness.compose(contract)
client = wrap_openai(OpenAI(), *harness.contracts)

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "..."}],
)

result = harness.validate(response.choices[0].message.content)
print(result["MyDomain"]["ok"])
```

### With async judge

```python
import asyncio
from codagent.harness import MetaAgentContract
from anthropic import AsyncAnthropic

async def judge_call_async(prompt: str) -> str:
    client = AsyncAnthropic()
    response = await client.messages.create(
        model="claude-opus-4-5",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text

# Wrap for sync use
def judge_call(prompt: str) -> str:
    return asyncio.run(judge_call_async(prompt))

contract = MetaAgentContract(
    name="MyDomain",
    judge_callable=judge_call,
    judge_prompt_template="...",
    compliance_marker="OK",
)
```

### With local LLM judge

```python
from codagent.harness import MetaAgentContract
import requests

def judge_call(prompt: str) -> str:
    # Call a local Ollama instance
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={"model": "mistral", "prompt": prompt, "stream": False},
    )
    return response.json()["response"]

contract = MetaAgentContract(
    name="LocalJudge",
    judge_callable=judge_call,
    judge_prompt_template="...",
    compliance_marker="COMPLIANT",
)
```

---

## See also

- [Harness Module](../modules/harness.md)
- [Behavior Contracts Guide](behavior-contracts.md)
- [Production Hardening Guide](production-hardening.md)
