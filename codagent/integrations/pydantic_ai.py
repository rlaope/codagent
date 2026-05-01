"""Adapter: feed a codagent Harness into a Pydantic AI Agent.

Pydantic AI's ``Agent`` takes a ``system_prompt`` parameter (str). The
simplest integration is a helper that returns a string you can pass
directly. The validator side (response checking) is run separately by
calling ``harness.validate(result.data)``.

Usage:

    from pydantic_ai import Agent
    from codagent.harness import Harness, AssumptionSurface
    from codagent.integrations import pydantic_ai_prompt

    h = Harness.compose(AssumptionSurface(min_items=2))

    agent = Agent(
        "openai:gpt-4o",
        system_prompt=pydantic_ai_prompt(h, base="You are a helpful assistant."),
    )

    result = agent.run_sync("Add an export feature")
    check = h.validate(result.data)  # {'AssumptionSurface': {...}, 'all_ok': bool}
"""

from __future__ import annotations

from codagent.harness._harness import Harness


def pydantic_ai_prompt(harness: Harness, *, base: str = "") -> str:
    """Return a system-prompt string with the harness addendum appended.

    Args:
        harness: composed Harness whose addendum will be injected
        base: existing system prompt to keep above the harness rules
    """
    addendum = harness.system_addendum()
    if base and addendum:
        return f"{base.strip()}\n\n{addendum}"
    return addendum or base
