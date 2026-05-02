"""``parse_structured`` — coerce node output into a typed object.

Accepts any one-arg callable as ``parser`` (typically a Pydantic model
class, or a custom validator). Keeps codagent free of a hard Pydantic
dependency.
"""

from __future__ import annotations

import json
from typing import Any, Callable


def parse_structured(parser: Callable[[Any], Any]) -> Callable[[Callable], Callable]:
    """Decorator factory: parse a node's output through ``parser``.

    Usage with Pydantic:

        from pydantic import BaseModel

        class Result(BaseModel):
            ok: bool
            answer: str

        @parse_structured(lambda d: Result(**d))
        def my_node(state): ...

    The wrapper handles common return shapes:
      - dict        -> parser(dict)
      - JSON string -> json.loads then parser(parsed)
      - already a parser-shaped instance -> returned as-is
    """
    def decorator(node: Callable) -> Callable:
        def wrapper(state):
            raw = node(state)
            if isinstance(raw, str):
                raw = json.loads(raw)
            return parser(raw)

        wrapper.__wrapped__ = node  # type: ignore[attr-defined]
        return wrapper

    return decorator
