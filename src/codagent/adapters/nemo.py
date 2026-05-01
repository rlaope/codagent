"""Adapter stub for NVIDIA NeMo Guardrails.

Requires the ``nemoguardrails`` extra:

    pip install codagent[nemo]

Wraps a NeMo ``LLMRails`` config or a single Colang flow into a
codagent Contract. The flow's intent becomes the system addendum;
validation runs the rails check.
"""

from __future__ import annotations

from codagent._abc import Contract, HarnessSource


class _NemoContract(Contract):
    def __init__(self, rails, intent: str = "", name: str | None = None):
        self.name = name or "nemo"
        self._rails = rails
        self._intent = intent or (
            "Follow the NeMo Guardrails policy attached to this session."
        )

    def system_addendum(self) -> str:
        return self._intent

    def validate(self, response: str) -> tuple[bool, str]:
        # NeMo rails operate at session-level; offline single-shot
        # validation is best-effort. Return True with a note if the
        # rails object exposes no straightforward check.
        check = getattr(self._rails, "check", None)
        if callable(check):
            try:
                ok = check(response)
                return bool(ok), "" if ok else "nemo rails reported failure"
            except Exception as e:
                return False, str(e)
        return True, "no offline check available"


class from_nemo(HarnessSource):
    """Wrap a NeMo LLMRails / Colang flow as a codagent HarnessSource."""

    def __init__(self, rails, intent: str = "", name: str | None = None):
        self._rails = rails
        self._intent = intent
        self.name = name or "from_nemo"

    def load(self) -> list[Contract]:
        return [_NemoContract(self._rails, self._intent, name=self.name)]
