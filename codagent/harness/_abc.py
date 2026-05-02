"""Abstract base protocols.

Contract       — a single behavioral rule (system addendum + validator)
HarnessSource  — produces a list of Contracts from an external source
                 (markdown file, URL, third-party harness library)
ApplyTarget    — consumes Contracts and writes them to a runtime
                 (Claude Code project, Cursor rules, OpenAI client wrap)
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class Contract(ABC):
    """A behavioral rule injected into LLM calls.

    Concrete contracts contribute (a) text to the system prompt and
    (b) a validator that checks whether a response complied.
    """

    name: str = "unnamed"

    @abstractmethod
    def system_addendum(self) -> str:
        """Text appended to the system prompt at call site."""

    @abstractmethod
    def validate(self, response: str) -> tuple[bool, str]:
        """Check if the response complies. Returns (ok, reason)."""


class HarnessSource(ABC):
    """Produces Contracts from an external source.

    Implementations: load CLAUDE.md / AGENTS.md / .cursor/rules,
    wrap a Guardrails.ai validator, parse a NeMo Colang flow, etc.
    """

    name: str = "unnamed-source"

    @abstractmethod
    def load(self) -> list[Contract]:
        """Return the contracts produced by this source."""


class ApplyTarget(ABC):
    """Consumes Contracts and applies them to a runtime environment.

    Implementations: write a project-level CLAUDE.md, write Cursor rules,
    wrap an OpenAI client, etc.
    """

    name: str = "unnamed-target"

    @abstractmethod
    def apply(self, contracts: list[Contract]) -> None:
        """Apply the given contracts to this target."""
