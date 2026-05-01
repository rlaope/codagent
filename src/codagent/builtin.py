"""Built-in Karpathy-derived contracts.

These are reference implementations of the Contract abstract — useful
on their own and as examples for how to build custom contracts. The
runtime contract pattern is more important than these specific rules.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from codagent._abc import Contract


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
            "- Using JSON format (CSV would need explicit column schema)\n"
            "- Hard limit at 10k rows per request (memory)\n\n"
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
