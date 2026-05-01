# Nodes

Composable wrappers for node callables: `with_retry`, `with_timeout`, `with_cache`, `parse_structured`. Stack them freely on any state-to-state callable.

## Overview

Each wrapper takes a callable (a function that maps state to state update) and returns a wrapped callable. They work with any state shape — not just LangGraph. You can chain them:

```python
from codagent.nodes import with_retry, with_timeout, with_cache

node = with_retry(
    with_timeout(
        with_cache(my_node, key_fn=lambda s: s["query"], ttl=300),
        seconds=30,
    ),
    attempts=3,
)
```

## `with_retry`

Retry a node on listed exception types with exponential backoff.

**Signature:**

```python
def with_retry(
    node: Callable,
    *,
    attempts: int = 3,
    backoff: float = 1.0,
    backoff_factor: float = 2.0,
    on: tuple[type[BaseException], ...] = (Exception,),
) -> Callable:
```

**Arguments:**

- `node`: Callable to wrap (state → state-update)
- `attempts`: Total attempts including the first try (>= 1)
- `backoff`: Initial sleep seconds before second attempt
- `backoff_factor`: Multiplier between attempts (2.0 = exponential)
- `on`: Tuple of exception types that trigger a retry

**Returns:** Wrapped callable. Raises the last seen exception if all attempts fail.

**Example:**

```python
from codagent.nodes import with_retry

def flaky_node(state):
    import random
    if random.random() < 0.5:
        raise ConnectionError("network glitch")
    return {"done": True}

robust = with_retry(
    flaky_node,
    attempts=3,
    backoff=0.5,
    backoff_factor=2.0,
    on=(ConnectionError,),
)

result = robust({})  # Retries up to 3 times
```

**Gotchas:**

- Catches only the exception types in `on`. Other exceptions pass through immediately.
- Sleeps on the main thread — avoid very large `attempts` or `backoff` values in latency-sensitive code.

---

## `with_timeout`

Bound a node's wall-clock execution with a thread-based timeout.

**Signature:**

```python
def with_timeout(node: Callable, *, seconds: float) -> Callable:
```

**Arguments:**

- `node`: Callable to wrap
- `seconds`: Timeout in seconds (> 0)

**Returns:** Wrapped callable. Raises `NodeTimeout` if the call exceeds the limit.

**Example:**

```python
from codagent.nodes import with_timeout, NodeTimeout

def slow_node(state):
    import time
    time.sleep(10)
    return state

guarded = with_timeout(slow_node, seconds=2)

try:
    guarded({})
except NodeTimeout as e:
    print(f"Timed out: {e}")  # Timed out: node exceeded 2s timeout
```

**Gotchas:**

- Uses `concurrent.futures.ThreadPoolExecutor`, so the timeout works cross-platform and inside any thread (signal-based timeouts are limited to the main thread on Unix).
- When a node times out, the inner thread is not forcibly killed — Python cannot safely kill threads — so the timed-out node continues to run in the background until it completes naturally. Monitor memory usage in production if nodes are long-lived.
- Thread cleanup may leak resources in v0.4.0; avoid stacking many timeouts on the same graph path.

---

## `with_cache`

In-memory LRU cache for node results with optional TTL.

**Signature:**

```python
def with_cache(
    node: Callable,
    *,
    key_fn: Callable[[Any], Hashable],
    ttl: float | None = None,
    max_size: int = 128,
) -> Callable:
```

**Arguments:**

- `node`: Callable to wrap
- `key_fn`: Function to extract a hashable cache key from state
- `ttl`: Seconds before a cache entry expires (None = no expiry)
- `max_size`: LRU eviction threshold

**Returns:** Wrapped callable. Hits cache on key match; evicts least-recently-used on overflow.

**Example:**

```python
from codagent.nodes import with_cache

def expensive_query(state):
    # Simulates a database query
    return {"result": state["query"] + " result"}

cached = with_cache(
    expensive_query,
    key_fn=lambda s: s.get("query"),  # Cache key is just the query
    ttl=300,  # 5 minutes
    max_size=256,
)

result1 = cached({"query": "python"})
result2 = cached({"query": "python"})  # Cache hit, no computation

# Access cache directly if needed
print(len(cached.cache))  # 1 entry
```

**Gotchas:**

- `key_fn` must return a hashable value (str, int, tuple, etc.). Complex objects cause errors.
- Cache is not thread-safe in v0.4.0. Wrap with a lock if your graph runs threads on the same node.
- TTL uses `time.monotonic()`, so clocks skew won't corrupt expiry — but the cache uses wall-clock time internally and respects system clock changes.

---

## `parse_structured`

Coerce a node's output into a typed object via a callable parser.

**Signature:**

```python
def parse_structured(parser: Callable[[Any], Any]) -> Callable[[Callable], Callable]:
```

**Arguments:**

- `parser`: One-arg callable that transforms raw output into typed output (typically a Pydantic model class or custom validator)

**Returns:** Decorator factory. Decorate a node with `@parse_structured(parser)`.

**Example with Pydantic:**

```python
from pydantic import BaseModel
from codagent.nodes import parse_structured

class ExportResult(BaseModel):
    ok: bool
    format: str
    rows: int

@parse_structured(lambda d: ExportResult(**d))
def my_node(state):
    # Return a dict or JSON string
    return {
        "ok": True,
        "format": "json",
        "rows": 42,
    }

result = my_node({})
print(result)  # ExportResult(ok=True, format='json', rows=42)
print(type(result))  # <class '__main__.ExportResult'>
```

**Handles multiple return shapes:**

- Dict → `parser(dict)` — caller chooses unpacking with `**` or not
- JSON string → `json.loads` then `parser(parsed)`
- Already a parser-shaped instance → returned as-is

**Example with custom validator:**

```python
from codagent.nodes import parse_structured

def validate_export(raw):
    if not isinstance(raw, dict):
        raise ValueError("expected dict")
    if "rows" not in raw or raw["rows"] < 0:
        raise ValueError("rows must be non-negative")
    return raw

@parse_structured(validate_export)
def my_node(state):
    return {"rows": 100}

result = my_node({})
print(result)  # {'rows': 100}
```

**Gotchas:**

- The parser is called with the entire parsed object, not unpacked with `**`. If you want `**` unpacking, define a wrapper: `parse_structured(lambda d: MyModel(**d))`.
- JSON parsing happens automatically; if your node returns a dict, the parser receives the dict directly.
- No type checking at call time — invalid output only fails when the parser raises.

---

## Stacking patterns

**All at once:**

```python
from codagent.nodes import with_retry, with_timeout, with_cache, parse_structured
from pydantic import BaseModel

class Result(BaseModel):
    data: str

@parse_structured(lambda d: Result(**d))
def my_node(state):
    return {"data": state.get("query", "default")}

# Cache → Timeout → Retry (order matters: innermost runs first)
production_node = with_retry(
    with_timeout(
        with_cache(
            my_node,
            key_fn=lambda s: s.get("query"),
            ttl=300,
        ),
        seconds=10,
    ),
    attempts=3,
    backoff=0.5,
)
```

Order matters: the outermost wrapper is the first handler on retry, the innermost is closest to the node. Choose order based on where you want recovery:

- `with_retry(with_timeout(...))`: Retry the whole timeout; useful if network is flaky.
- `with_timeout(with_retry(...))`: Timeout the retries; useful if you want a hard deadline.

**In LangGraph:**

```python
from langgraph.graph import StateGraph

graph = StateGraph(...)
graph.add_node("query", production_node)  # Just works
```

---

## See also

- [Observability](observability.md) — Guard loops with `StepBudget`
- [Production Hardening](../guides/production-hardening.md) — Combine nodes with tools and observability
