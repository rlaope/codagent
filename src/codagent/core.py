"""Core primitives.

Each primitive contributes (a) a system-prompt addendum that shapes
agent behavior at the LLM call site and (b) a validator that checks
whether a response complied. Compose them with `Harness`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


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
class AssumptionSurface:
    """Force the agent to surface its assumptions before acting.

    When the user request leaves any decision unspecified (scope,
    format, scale, edge cases), the agent must lead with an
    `Assumptions:` block listing decisions in declarative form.
    """

    min_items: int = 1

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
        # Crude heuristic: count bullet items anywhere in response.
        items = len(_ASSUMPTION_ITEM_RE.findall(response))
        if items < self.min_items:
            return False, (
                f"found {items} bullet items, need at least {self.min_items}"
            )
        return True, ""


@dataclass
class VerificationLoop:
    """Force the agent to back any "done" claim with evidence.

    Evidence accepted: passing test, command output, or a diff that
    visibly satisfies the success criteria. Disallowed: phrases like
    "should work", "looks correct", "I believe".
    """

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


class Harness:
    """Compose multiple contracts into a single addendum + validator."""

    def __init__(self, *contracts):
        self.contracts = list(contracts)

    def system_addendum(self) -> str:
        parts = [c.system_addendum() for c in self.contracts]
        return "\n\n".join(p for p in parts if p)

    def wrap_messages(self, messages: list[dict]) -> list[dict]:
        addendum = self.system_addendum()
        if not addendum:
            return list(messages)
        if messages and messages[0].get("role") == "system":
            head = messages[0]
            new_head = {
                "role": "system",
                "content": (head.get("content") or "") + "\n\n" + addendum,
            }
            return [new_head, *messages[1:]]
        return [{"role": "system", "content": addendum}, *messages]

    def validate(self, response: str) -> dict:
        results = {}
        all_ok = True
        for c in self.contracts:
            name = type(c).__name__
            ok, msg = c.validate(response)
            results[name] = {"ok": ok, "reason": msg}
            if not ok:
                all_ok = False
        results["all_ok"] = all_ok
        return results
