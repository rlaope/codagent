"""Adapter stub: CrewAI integration.

Requires the ``crewai`` extra:

    pip install codagent[crewai]

Planned shape (v0.5.0):

    from crewai import Agent
    from codagent.integrations import crewai_agent_with_harness

    agent = crewai_agent_with_harness(
        base_agent=Agent(role="Researcher", goal="...", backstory="..."),
        harness=Harness.compose(CitationRequired()),
    )

Currently a placeholder — contributions welcome.
"""

from __future__ import annotations

from codagent.harness._harness import Harness


def crewai_agent_with_harness(*, base_agent, harness: Harness):
    """Append the harness addendum to a CrewAI Agent's backstory.

    Stub: simple field append. Replace with a proper Agent subclass when
    we add live validation hooks.
    """
    addendum = harness.system_addendum()
    existing_backstory = getattr(base_agent, "backstory", "") or ""
    new_backstory = (existing_backstory.strip() + "\n\n" + addendum).strip()
    try:
        base_agent.backstory = new_backstory
    except Exception:
        # Fall back: return a (backstory, agent) tuple so caller can
        # rebuild the Agent if it's frozen.
        return (new_backstory, base_agent)
    return base_agent
