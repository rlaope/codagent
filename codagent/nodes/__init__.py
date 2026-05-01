"""codagent.nodes — composable wrappers for LangGraph node callables.

Each wrapper takes a node (a callable that maps state to a partial
state update) and returns a wrapped callable. Stack them freely:

    node = with_retry(with_timeout(with_cache(my_node, key_fn=...),
                                   seconds=30),
                      attempts=3)

    graph.add_node("step", node)

The wrappers are framework-agnostic: they work on any ``state -> state``
callable, not just LangGraph nodes.
"""

from codagent.nodes.cache import with_cache
from codagent.nodes.retry import with_retry
from codagent.nodes.structured import parse_structured
from codagent.nodes.timeout import NodeTimeout, with_timeout

__all__ = [
    "NodeTimeout",
    "parse_structured",
    "with_cache",
    "with_retry",
    "with_timeout",
]
