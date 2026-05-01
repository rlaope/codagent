"""LangGraph integration — node factories.

`assumption_surface_node(model)` returns a callable usable as a
LangGraph node that runs `AssumptionSurface` against the agent's
upcoming action.

`verification_gate(state, evidence_field="evidence")` is a conditional
edge function that returns "verified" or "missing" based on whether
the state contains evidence.

These are thin shims over the core primitives — the heavy lifting
is in `codagent.builtin`.
"""

from __future__ import annotations

from codagent.builtin import AssumptionSurface, VerificationLoop


def assumption_surface_node(llm, *, min_items: int = 1):
    """Return a LangGraph node callable that asks the LLM for assumptions.

    The returned callable expects state with a `messages` list and adds
    a structured assumptions message before the next action. Wire it as
    an early node in your graph.
    """
    contract = AssumptionSurface(min_items=min_items)

    def node(state):
        messages = list(state.get("messages", []))
        addendum = {"role": "system", "content": contract.system_addendum()}
        return {"messages": [addendum, *messages]}

    return node


def verification_gate(state, *, evidence_field: str = "evidence") -> str:
    """Conditional-edge function: 'verified' if state has evidence, else 'missing'.

    Use with graph.add_conditional_edges:

        graph.add_conditional_edges(
            "execute",
            verification_gate,
            {"verified": "done", "missing": "retry"},
        )
    """
    contract = VerificationLoop()
    last = ""
    if isinstance(state, dict):
        if evidence_field in state and state[evidence_field]:
            return "verified"
        msgs = state.get("messages") or []
        if msgs:
            last = msgs[-1].get("content", "") if isinstance(msgs[-1], dict) else str(msgs[-1])
    ok, _ = contract.validate(last)
    return "verified" if ok else "missing"


__all__ = ["assumption_surface_node", "verification_gate"]
