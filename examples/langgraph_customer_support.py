"""Example: customer-support agent on LangGraph with codagent harness.

Demonstrates plugging two contracts into a LangGraph workflow:
    - RefusalPattern    refuses sensitive requests with explicit blocks
    - ToolCallSurface   forces the agent to declare tool intent

This file uses pseudocode where LangGraph internals would be — the
goal is to show the SHAPE of integration, not run a real graph.
"""

from codagent import Harness, RefusalPattern, ToolCallSurface
from codagent.langgraph_nodes import assumption_surface_node


def build_harness() -> Harness:
    """Domain harness for customer-support agents."""
    return Harness.compose(
        RefusalPattern(
            sensitive_keywords=(
                "legal-advice",
                "medical-advice",
                "share my password",
            )
        ),
        ToolCallSurface(),
    )


def example_graph_wiring(graph, llm):
    """Pseudocode: how you'd wire codagent into a real LangGraph.

    Replace `graph` with a `StateGraph` and `llm` with your provider.
    """
    harness = build_harness()

    # Inject harness as an early node — every state arrives at the
    # "clarify" node first, picking up the harness system addendum.
    graph.add_node("clarify", assumption_surface_node(llm, min_items=1))
    graph.add_edge("clarify", "tool_dispatch")

    # The model node receives the augmented state with harness rules
    # already applied via the harness's system addendum.
    return graph


if __name__ == "__main__":
    h = build_harness()
    print("composed customer-support harness:")
    for c in h.contracts:
        print(f"  - {c.name}")
    print()
    print("system addendum length:", len(h.system_addendum()), "chars")
