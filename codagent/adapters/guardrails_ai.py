"""Adapter stub for Guardrails.ai validators.

Requires the ``guardrails`` extra:

    pip install codagent[guardrails-ai]

Wraps a Guardrails.ai ``Guard`` or validator into a codagent Contract.
The contract's system addendum prompts the agent to comply with the
validator's intent; the validator runs as the codagent validate().
"""

from __future__ import annotations

from codagent._abc import Contract, HarnessSource


class _GuardrailsContract(Contract):
    def __init__(self, guard, name: str | None = None):
        self.name = name or f"guardrails:{type(guard).__name__}"
        self._guard = guard

    def system_addendum(self) -> str:
        # Generic addendum — Guardrails specs are validator-shaped, not
        # behavior-shaped. Concrete projects can override.
        return (
            "Your output will be checked by an automated validator. "
            "Comply with the documented schema and content rules."
        )

    def validate(self, response: str) -> tuple[bool, str]:
        try:
            self._guard.validate(response)
            return True, ""
        except Exception as e:
            return False, str(e)


class from_guardrails_ai(HarnessSource):
    """Wrap a Guardrails.ai Guard as a codagent HarnessSource."""

    def __init__(self, guard, name: str | None = None):
        self._guard = guard
        self.name = name or "from_guardrails_ai"

    def load(self) -> list[Contract]:
        return [_GuardrailsContract(self._guard, name=self.name)]
