"""Built-in Contract implementations.

These cover the major agent behavior categories codagent targets:

  Karpathy (general):
      AssumptionSurface, VerificationLoop

  Tool-use (agentic systems):
      ToolCallSurface

  Conversational / domain compliance:
      RefusalPattern, CitationRequired

  Meta-agent (domain agent injected as harness):
      MetaAgentContract
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

from codagent.harness._abc import Contract


# -- Karpathy core ----------------------------------------------------------

_ASSUMPTION_HEADING_RE = re.compile(r"(?im)^\s*[*#]*\s*Assumptions?\b\s*[:\s]")
_ASSUMPTION_ITEM_RE = re.compile(r"(?m)^\s*[-*]\s+\S")

_EVIDENCE_RE = re.compile(
    r"(?im)("
    r"\btest(?:s)?\s+passed\b|"
    r"\ball\s+tests?\s+pass\b|"
    r"^\s*\$\s+\S+|"
    r"\bexit\s+code\s+0\b|"
    r"\boutput:|"
    r"\bverified\s+by\s+running\b|"
    r"\bi\s+(?:ran|executed)\b"
    r")",
)
_UNBACKED_RE = re.compile(
    r"(?i)\b(should\s+work|looks?\s+correct|i\s+believe|"
    r"this\s+ought\s+to|presumably\s+works|appears\s+correct)\b",
)


@dataclass
class AssumptionSurface(Contract):
    """Force the agent to surface its assumptions before acting."""

    min_items: int = 1
    name: str = "AssumptionSurface"

    def system_addendum(self) -> str:
        return (
            "When the user's request leaves any decision unspecified "
            "(scope, format, scale, edge cases, target audience), prepend "
            "your response with an `Assumptions:` block listing the "
            "decisions you're making, in declarative form. Each item is "
            "specific and corrigible.\n\n"
            "Example:\n"
            "Assumptions:\n"
            "- Treating \"users\" as active users only (excluding soft-deleted)\n"
            "- Using JSON format (CSV would need explicit column schema)\n\n"
            "Each item is something the user can correct in one word."
        )

    def validate(self, response: str) -> tuple[bool, str]:
        if not _ASSUMPTION_HEADING_RE.search(response):
            return False, "no `Assumptions:` heading found"
        items = len(_ASSUMPTION_ITEM_RE.findall(response))
        if items < self.min_items:
            return False, f"found {items} bullet items, need at least {self.min_items}"
        return True, ""


@dataclass
class VerificationLoop(Contract):
    """Force the agent to back any 'done' claim with evidence."""

    name: str = "VerificationLoop"

    def system_addendum(self) -> str:
        return (
            "Before declaring any task done, complete, fixed, or ready, "
            "produce one of:\n"
            "  - A passing test you wrote (preferred)\n"
            "  - A command output (build, lint, run) showing the new behavior\n"
            "  - A diff that visibly satisfies the stated success criteria\n\n"
            "If you cannot verify, say so explicitly: "
            "\"I have not verified this. Specifically: I did not run X "
            "because Y.\"\n\n"
            "Never use \"should work\", \"looks correct\", or "
            "\"I believe\" as a substitute for evidence."
        )

    def validate(self, response: str) -> tuple[bool, str]:
        if _UNBACKED_RE.search(response):
            return False, "unbacked claim phrase detected"
        if not _EVIDENCE_RE.search(response) and "i have not verified" not in response.lower():
            return False, "no evidence markers and no honest 'not verified' note"
        return True, ""


# -- Tool-use ---------------------------------------------------------------

_TOOLCALL_HEADING_RE = re.compile(r"(?im)^\s*[*#]*\s*ToolCall\s*[:\s]")


@dataclass
class ToolCallSurface(Contract):
    """Force the agent to declare tool intent before invoking a tool.

    Use in tool-use / function-calling agents (LangGraph, LangChain
    agents, OpenAI assistants). The agent must articulate which tool,
    why, and what it expects — preventing silent tool spam.
    """

    name: str = "ToolCallSurface"

    def system_addendum(self) -> str:
        return (
            "Before invoking any tool, prepend a `ToolCall:` block stating:\n"
            "  - which tool you are about to call\n"
            "  - why this tool, not another\n"
            "  - what you expect to learn or change\n\n"
            "Example:\n"
            "ToolCall:\n"
            "  tool: search_orders\n"
            "  why: user mentioned 'last order' but no id; need to find theirs\n"
            "  expect: 0-3 recent orders for this customer\n\n"
            "If you are sure the request needs no tool, say so explicitly "
            "and answer directly."
        )

    def validate(self, response: str) -> tuple[bool, str]:
        # We only enforce: if the response mentions executing a tool, a
        # ToolCall: block must appear. Inferring tool calls from text is
        # fragile, so this is a best-effort check.
        looks_like_tool_call = bool(
            re.search(r"(?i)\b(calling|invoking|executing|using)\s+(the\s+)?\w+\s+tool", response)
        )
        if looks_like_tool_call and not _TOOLCALL_HEADING_RE.search(response):
            return False, "tool invocation hinted but no `ToolCall:` block found"
        return True, ""


# -- Conversational / domain ------------------------------------------------

_REFUSAL_HEADING_RE = re.compile(r"(?im)^\s*[*#]*\s*Refusal\s*[:\s]")


@dataclass
class RefusalPattern(Contract):
    """Force explicit refusal blocks for sensitive request categories.

    When the request touches any of `sensitive_keywords`, the agent
    must respond with a `Refusal:` block stating the reason rather
    than silently complying or giving a wishy-washy 'I'm not sure'.
    """

    sensitive_keywords: tuple[str, ...] = field(default_factory=tuple)
    name: str = "RefusalPattern"

    def system_addendum(self) -> str:
        kw = ", ".join(self.sensitive_keywords) if self.sensitive_keywords else "[domain-specific]"
        return (
            f"If the user's request touches any of: {kw}, "
            f"you MUST refuse with a `Refusal:` block stating:\n"
            f"  - the policy or principle you are invoking\n"
            f"  - what alternative action the user can take\n\n"
            f"Do not partially comply, do not hedge. Refusal blocks are "
            f"explicit and machine-readable so calling code can branch on them."
        )

    def validate(self, response: str) -> tuple[bool, str]:
        # If response does not mention sensitive keywords, contract passes
        # vacuously. Otherwise, demand a Refusal: block.
        if not self.sensitive_keywords:
            return True, ""
        rl = response.lower()
        touched = [k for k in self.sensitive_keywords if k.lower() in rl]
        if touched and not _REFUSAL_HEADING_RE.search(response):
            return False, f"sensitive keyword(s) present {touched} but no `Refusal:` block"
        return True, ""


_CITATION_RE = re.compile(r"\[source:[^\]]+\]")


@dataclass
class CitationRequired(Contract):
    """Force every factual claim to carry a `[source: ...]` marker.

    Use for research, legal, medical, or compliance domains where
    unsourced claims are unacceptable. Honest 'not verified' is OK.
    """

    min_citations: int = 1
    name: str = "CitationRequired"

    def system_addendum(self) -> str:
        return (
            "Every factual claim in your response must be followed by "
            "`[source: <name or URL or 'not verified'>]`. If you don't "
            "have a source, write `[source: not verified]` rather than "
            "leaving the claim bare. Opinions and reasoning steps don't "
            "need citations — only factual claims."
        )

    def validate(self, response: str) -> tuple[bool, str]:
        n = len(_CITATION_RE.findall(response))
        if n < self.min_citations:
            return False, f"found {n} citation markers, need at least {self.min_citations}"
        return True, ""


# -- Meta-agent (domain agent injected as harness) --------------------------


class MetaAgentContract(Contract):
    """A Contract whose validate() runs an LLM as judge.

    This is the 'domain agent injected as harness' primitive. The
    judge_callable is any function that takes a prompt string and
    returns a response string (your existing OpenAI/Anthropic/local
    LLM call). The judge is asked to evaluate the main agent's
    response for compliance with a domain rule.

    Use this when the rule is too nuanced for regex validation —
    e.g., "did the response give investment advice without proper
    disclaimers?", "did the medical answer cite a peer-reviewed
    source?", "did the customer service reply respect tone-of-voice
    guidelines?".
    """

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

    def system_addendum(self) -> str:
        return self._addendum

    def validate(self, response: str) -> tuple[bool, str]:
        prompt = self._template.format(response=response, marker=self._marker)
        judgment = (self._judge(prompt) or "").upper()
        marker_up = self._marker.upper()
        if re.search(rf"(NON-|NOT\s+){re.escape(marker_up)}", judgment):
            return False, f"meta-agent judgment: {judgment.strip()[:200]}"
        if marker_up in judgment:
            return True, ""
        return False, f"meta-agent judgment: {judgment.strip()[:200]}"
