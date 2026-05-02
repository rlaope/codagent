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


# -- Judge fallback (i18n / format-variant tolerance) -----------------------
#
# Regex contracts pass cheaply when the response is in English and uses the
# canonical block headings. If a ``judge`` callable is supplied, the contract
# falls back to LLM-as-judge when the regex check fails — which lets the
# contract accept "전제:", "前提:", "Hipótesis:" or other valid forms that
# regex cannot anticipate. The judge runs only on regex misses, so the cost
# is bounded by failure rate rather than call rate.

_JUDGE_YES_RE = re.compile(r"(?im)^\s*YES\b")
_JUDGE_NO_RE = re.compile(r"(?im)^\s*NO\b")


def _judge_yes_no(judge: Callable[[str], str], prompt: str) -> tuple[bool, str]:
    """Run a judge and parse a single-line YES / NO verdict."""
    verdict = (judge(prompt) or "").strip()
    if _JUDGE_NO_RE.match(verdict):
        return False, f"judge: {verdict[:200]}"
    if _JUDGE_YES_RE.match(verdict):
        return True, ""
    return False, f"judge unclear: {verdict[:200]}"


# -- Karpathy core ----------------------------------------------------------

_ASSUMPTION_HEADING_RE = re.compile(r"(?im)^\s*[*#]*\s*Assumptions?\b\s*[:\s]")
_ASSUMPTION_ITEM_RE = re.compile(r"(?m)^\s*[-*]\s+\S")

_EVIDENCE_RE = re.compile(
    r"(?im)("
    r"\b(?:py)?test(?:s)?\s+passed\b|"
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
    judge: Callable[[str], str] | None = None

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

    def _judge_prompt(self, response: str) -> str:
        return (
            "You are validating whether an LLM response surfaces assumptions "
            "before acting. The response should begin with an explicit list "
            "of assumptions (in any language; e.g. `Assumptions:`, `전제:`, "
            "`前提:`). It must contain at least "
            f"{self.min_items} assumption item(s).\n\n"
            f"RESPONSE:\n{response}\n\n"
            "Reply on a single line:\n"
            "  YES — if the response surfaces enough assumptions explicitly\n"
            "  NO: <reason> — otherwise"
        )

    def validate(self, response: str) -> tuple[bool, str]:
        if _ASSUMPTION_HEADING_RE.search(response):
            items = len(_ASSUMPTION_ITEM_RE.findall(response))
            if items >= self.min_items:
                return True, ""
            reason = f"found {items} bullet items, need at least {self.min_items}"
        else:
            reason = "no `Assumptions:` heading found"
        if self.judge is None:
            return False, reason
        return _judge_yes_no(self.judge, self._judge_prompt(response))


@dataclass
class VerificationLoop(Contract):
    """Force the agent to back any 'done' claim with evidence."""

    name: str = "VerificationLoop"
    judge: Callable[[str], str] | None = None

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

    def _judge_prompt(self, response: str) -> str:
        return (
            "You are validating whether an LLM response backs any 'done' "
            "claim with concrete evidence (test output, command output, diff) "
            "or honestly admits non-verification. Hand-wavy phrases like "
            "'should work' / 'looks correct' / 'I believe' do NOT count as "
            "evidence, in any language.\n\n"
            f"RESPONSE:\n{response}\n\n"
            "Reply on a single line:\n"
            "  YES — if evidence is present OR non-verification is admitted\n"
            "  NO: <reason> — if it claims completion without evidence"
        )

    def validate(self, response: str) -> tuple[bool, str]:
        if _UNBACKED_RE.search(response):
            reason = "unbacked claim phrase detected"
        elif not _EVIDENCE_RE.search(response) and "i have not verified" not in response.lower():
            reason = "no evidence markers and no honest 'not verified' note"
        else:
            return True, ""
        if self.judge is None:
            return False, reason
        return _judge_yes_no(self.judge, self._judge_prompt(response))


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
    judge: Callable[[str], str] | None = None

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

    def _judge_prompt(self, response: str) -> str:
        return (
            "You are validating whether an LLM response declares tool intent "
            "before invoking a tool. If a tool is invoked, a `ToolCall:` "
            "block (or equivalent in any language) must precede it stating "
            "which tool, why, and what to expect. If no tool is invoked, "
            "the response passes vacuously.\n\n"
            f"RESPONSE:\n{response}\n\n"
            "Reply on a single line:\n"
            "  YES — if no tool is invoked, or intent is declared first\n"
            "  NO: <reason> — if a tool is invoked silently"
        )

    def validate(self, response: str) -> tuple[bool, str]:
        looks_like_tool_call = bool(
            re.search(r"(?i)\b(calling|invoking|executing|using)\s+(the\s+)?\w+\s+tool", response)
        )
        if not looks_like_tool_call or _TOOLCALL_HEADING_RE.search(response):
            return True, ""
        reason = "tool invocation hinted but no `ToolCall:` block found"
        if self.judge is None:
            return False, reason
        return _judge_yes_no(self.judge, self._judge_prompt(response))


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
    judge: Callable[[str], str] | None = None

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

    def _judge_prompt(self, response: str, touched: list[str]) -> str:
        return (
            "You are validating whether an LLM response includes an explicit "
            "refusal block (in any language; e.g. `Refusal:`, `거절:`, "
            "`拒否:`) when the response touches sensitive topics. The block "
            "must state the policy invoked AND the user's alternative.\n\n"
            f"SENSITIVE TOPICS TOUCHED: {touched}\n"
            f"RESPONSE:\n{response}\n\n"
            "Reply on a single line:\n"
            "  YES — if the refusal is explicit (policy + alternative)\n"
            "  NO: <reason> — otherwise"
        )

    def validate(self, response: str) -> tuple[bool, str]:
        if not self.sensitive_keywords:
            return True, ""
        rl = response.lower()
        touched = [k for k in self.sensitive_keywords if k.lower() in rl]
        if not touched or _REFUSAL_HEADING_RE.search(response):
            return True, ""
        reason = f"sensitive keyword(s) present {touched} but no `Refusal:` block"
        if self.judge is None:
            return False, reason
        return _judge_yes_no(self.judge, self._judge_prompt(response, touched))


_CITATION_RE = re.compile(r"\[source:[^\]]+\]")


@dataclass
class CitationRequired(Contract):
    """Force every factual claim to carry a `[source: ...]` marker.

    Use for research, legal, medical, or compliance domains where
    unsourced claims are unacceptable. Honest 'not verified' is OK.
    """

    min_citations: int = 1
    name: str = "CitationRequired"
    judge: Callable[[str], str] | None = None

    def system_addendum(self) -> str:
        return (
            "Every factual claim in your response must be followed by "
            "`[source: <name or URL or 'not verified'>]`. If you don't "
            "have a source, write `[source: not verified]` rather than "
            "leaving the claim bare. Opinions and reasoning steps don't "
            "need citations — only factual claims."
        )

    def _judge_prompt(self, response: str) -> str:
        return (
            "You are validating whether an LLM response carries citations on "
            "every factual claim. Acceptable forms include `[source: ...]`, "
            "footnotes, inline URLs, or equivalent in any language (e.g. "
            "`[출처: ...]`, `[ソース: ...]`). The response must carry at "
            f"least {self.min_citations} citation(s).\n\n"
            f"RESPONSE:\n{response}\n\n"
            "Reply on a single line:\n"
            f"  YES — if at least {self.min_citations} citation(s) are present\n"
            "  NO: <reason> — otherwise"
        )

    def validate(self, response: str) -> tuple[bool, str]:
        n = len(_CITATION_RE.findall(response))
        if n >= self.min_citations:
            return True, ""
        reason = f"found {n} citation markers, need at least {self.min_citations}"
        if self.judge is None:
            return False, reason
        return _judge_yes_no(self.judge, self._judge_prompt(response))


# -- Meta-agent (domain agent injected as harness) --------------------------


_FAITHFULNESS_PROMPT = """You are a faithfulness judge for a retrieval-augmented \
answer.

CONTEXT (retrieved documents, separated by ---):
{context}

RESPONSE (the agent's answer):
{response}

Question: are ALL factual claims in RESPONSE supported by CONTEXT?
A claim is supported only if the same fact appears in CONTEXT — paraphrasing \
is fine, but new facts that are not in CONTEXT are not supported.

Reply on a single line, in this exact format:
  FAITHFUL  — if every factual claim is supported
  UNFAITHFUL: <one-sentence reason citing the unsupported claim>
"""


@dataclass
class FaithfulnessContract(Contract):
    """LLM-as-judge contract for RAG grounding (RAGAS-style faithfulness).

    Validates that every factual claim in the agent's response is
    supported by retrieved context. Catches the failure mode where
    ``CitationRequired`` passes (markers present) but the cited fact
    was actually hallucinated and the citation is decorative.

    Stateful by design: call :meth:`set_context` after retrieval and
    before validation. Pass ``context_provider`` to read context lazily
    instead (useful when Harness lifecycle is fixed).

    Example:

        judge = lambda p: openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": p}],
        ).choices[0].message.content
        faith = FaithfulnessContract(judge=judge)
        harness = Harness.compose(CitationRequired(), faith)

        # in retrieve node: faith.set_context([d.text for d in docs])
        # in validate: harness.validate(answer)
    """

    judge: Callable[[str], str] | None = None
    name: str = "Faithfulness"
    context_provider: Callable[[], str | list[str] | None] | None = None
    _current_context: str = field(default="", init=False, repr=False)

    def set_context(self, context: str | list[str] | None) -> None:
        """Inject retrieved context for the next validation call."""
        if context is None:
            self._current_context = ""
            return
        if isinstance(context, list):
            self._current_context = "\n---\n".join(str(c) for c in context)
        else:
            self._current_context = str(context)

    def _resolve_context(self) -> str:
        if self.context_provider is not None:
            ctx = self.context_provider()
            if ctx is None:
                return ""
            if isinstance(ctx, list):
                return "\n---\n".join(str(c) for c in ctx)
            return str(ctx)
        return self._current_context

    def system_addendum(self) -> str:
        return (
            "Every factual claim in your response must be supported by the "
            "retrieved context (the documents the system put in front of you). "
            "Do not introduce facts that are not in the context. If the "
            "context lacks the information needed for a claim, say so "
            "explicitly rather than inventing or speculating."
        )

    def validate(self, response: str) -> tuple[bool, str]:
        if self.judge is None:
            return True, "faithfulness skipped: no judge configured"
        context = self._resolve_context()
        if not context:
            return True, "faithfulness skipped: no context provided"
        prompt = _FAITHFULNESS_PROMPT.format(context=context, response=response)
        verdict = (self.judge(prompt) or "").strip()
        upper = verdict.upper()
        if re.search(r"\bUNFAITHFUL\b|\bNOT\s+FAITHFUL\b", upper):
            return False, f"unfaithful: {verdict[:200]}"
        if "FAITHFUL" in upper:
            return True, ""
        return False, f"unclear faithfulness verdict: {verdict[:200]}"


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
        judgment = self._judge(prompt) or ""
        upper = judgment.upper()
        marker_up = self._marker.upper()
        if re.search(rf"(NON-|NOT\s+){re.escape(marker_up)}", upper):
            return False, f"meta-agent judgment: {judgment.strip()[:200]}"
        if marker_up in upper:
            return True, ""
        return False, f"meta-agent judgment: {judgment.strip()[:200]}"
