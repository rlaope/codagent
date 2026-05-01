"""``with_cache`` — in-memory LRU cache for node results.

Unlike LangGraph's native input-hash cache, this lets you supply your
own ``key_fn`` so you can cache on a semantic key (e.g. just the user
query) instead of the entire state hash.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any, Callable, Hashable


def with_cache(
    node: Callable,
    *,
    key_fn: Callable[[Any], Hashable],
    ttl: float | None = None,
    max_size: int = 128,
) -> Callable:
    """Wrap a node with an LRU result cache.

    Args:
        node: callable to wrap
        key_fn: state -> hashable cache key
        ttl: seconds before a cache entry expires (None = no expiry)
        max_size: LRU eviction threshold

    Stores ``(value, expiry_or_None)`` per key.
    """
    if max_size < 1:
        raise ValueError("max_size must be >= 1")

    cache: OrderedDict[Hashable, tuple[Any, float | None]] = OrderedDict()

    def wrapper(state):
        key = key_fn(state)
        now = time.monotonic()
        if key in cache:
            value, expiry = cache[key]
            if expiry is None or expiry > now:
                cache.move_to_end(key)
                return value
            del cache[key]

        value = node(state)
        expiry = (now + ttl) if ttl is not None else None
        cache[key] = (value, expiry)
        cache.move_to_end(key)
        while len(cache) > max_size:
            cache.popitem(last=False)
        return value

    wrapper.__wrapped__ = node  # type: ignore[attr-defined]
    wrapper.cache = cache  # type: ignore[attr-defined]
    return wrapper
