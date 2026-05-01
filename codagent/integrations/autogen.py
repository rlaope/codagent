"""Adapter stub: AutoGen integration.

Requires the ``autogen`` extra:

    pip install codagent[autogen]

Planned shape (v0.5.0):

    from autogen import AssistantAgent
    from codagent.integrations import autogen_assistant_with_harness

    agent = autogen_assistant_with_harness(
        base=AssistantAgent("worker", llm_config={...}),
        harness=harness,
    )

Currently a placeholder — contributions welcome.
"""

from __future__ import annotations

from codagent.harness._harness import Harness


def autogen_assistant_with_harness(*, base, harness: Harness):
    """Append the harness addendum to an AutoGen agent's system_message.

    Stub: simple field append.
    """
    addendum = harness.system_addendum()
    existing = getattr(base, "system_message", "") or ""
    try:
        base.update_system_message((existing.strip() + "\n\n" + addendum).strip())
    except Exception:
        # AutoGen versions vary; fall back to setting attribute directly.
        try:
            base.system_message = (existing.strip() + "\n\n" + addendum).strip()
        except Exception:
            pass
    return base
