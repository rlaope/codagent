"""``validated_tool`` — kwargs validation before a tool fires.

Accepts any one-arg callable as ``validator`` (commonly a Pydantic
model class). The validator is called with the kwargs dict; whatever
it returns is unpacked and passed to the underlying tool.

Pydantic example:

    from pydantic import BaseModel

    class SearchArgs(BaseModel):
        query: str
        limit: int = 10

    @validated_tool(lambda kw: SearchArgs(**kw).model_dump())
    def search_db(query: str, limit: int = 10): ...
"""

from __future__ import annotations

from typing import Any, Callable


def validated_tool(
    validator: Callable[[dict[str, Any]], dict[str, Any]],
) -> Callable[[Callable], Callable]:
    """Decorator factory: validate tool kwargs through ``validator``."""
    def decorator(fn: Callable) -> Callable:
        def wrapper(**kwargs):
            validated = validator(kwargs)
            if not isinstance(validated, dict):
                raise TypeError(
                    f"validator must return a dict, got {type(validated).__name__}"
                )
            return fn(**validated)
        wrapper.__wrapped__ = fn  # type: ignore[attr-defined]
        return wrapper
    return decorator
