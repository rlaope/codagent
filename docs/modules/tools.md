# Tools

Decorators for hardening tool callables: `validated_tool`, `circuit_breaker`, `rate_limit`. Stack them freely on any tool function.

## Overview

Each decorator wraps a tool (a callable that agents call) and returns a hardened version. They compose naturally:

```python
from codagent.tools import validated_tool, circuit_breaker, rate_limit

@validated_tool(validate_args)
@circuit_breaker(failure_threshold=5, reset_after=60)
@rate_limit(per_second=10)
def search_db(query: str, limit: int = 10):
    pass  # tool implementation
```

## `validated_tool`

Validate tool kwargs before calling the underlying function.

**Signature:**

```python
def validated_tool(
    validator: Callable[[dict[str, Any]], dict[str, Any]],
) -> Callable[[Callable], Callable]:
```

**Arguments:**

- `validator`: One-arg callable that takes a kwargs dict and returns a validated/transformed dict

**Returns:** Decorator factory. Decorate a tool with `@validated_tool(validator)`.

**Example with Pydantic:**

```python
from pydantic import BaseModel
from codagent.tools import validated_tool

class SearchArgs(BaseModel):
    query: str
    limit: int = 10

    def validate(self):
        if not self.query.strip():
            raise ValueError("query cannot be empty")
        if self.limit < 1 or self.limit > 100:
            raise ValueError("limit must be 1-100")
        return self.model_dump()

@validated_tool(lambda kw: SearchArgs(**kw).validate())
def search_db(query: str, limit: int = 10):
    return f"results for {query} (max {limit})"

result = search_db(query="python", limit=5)
# Valid: returns "results for python (max 5)"

try:
    search_db(query="", limit=10)  # Pydantic or ValueError before tool runs
except ValueError:
    pass
```

**Simple validator without Pydantic:**

```python
def validate_search(kwargs):
    if "query" not in kwargs or not kwargs["query"]:
        raise ValueError("query is required")
    limit = int(kwargs.get("limit", 10))
    if limit < 1 or limit > 100:
        raise ValueError("limit out of range")
    return {"query": kwargs["query"], "limit": limit}

@validated_tool(validate_search)
def search_db(query: str, limit: int = 10):
    pass
```

**Gotchas:**

- Validator must return a dict. If it returns anything else, a `TypeError` is raised.
- The validator sees all kwargs as passed by the caller, even if some have defaults — be explicit about which are required.

---

## `circuit_breaker`

Fast-fail a tool after N consecutive failures.

**Signature:**

```python
def circuit_breaker(
    *,
    failure_threshold: int = 5,
    reset_after: float = 60.0,
) -> Callable[[Callable], Callable]:
```

**Arguments:**

- `failure_threshold`: Number of consecutive failures before opening (>= 1)
- `reset_after`: Seconds to wait before trying again

**Returns:** Decorator factory. Decorate a tool with `@circuit_breaker(...)`.

**State machine:**

- `CLOSED`: Normal operation; calls pass through
- `OPEN`: After N failures, fast-fail with `CircuitBreakerOpen` for `reset_after` seconds
- `HALF_OPEN`: One trial call after cooldown; success closes, fail re-opens

**Example:**

```python
from codagent.tools import circuit_breaker, CircuitBreakerOpen

@circuit_breaker(failure_threshold=3, reset_after=60)
def call_flaky_api(endpoint: str):
    import random
    if random.random() < 0.7:
        raise Exception("API timeout")
    return {"status": "ok"}

# After 3 consecutive failures, the circuit opens
for i in range(5):
    try:
        call_flaky_api("users")
    except CircuitBreakerOpen as e:
        print(f"Breaker open: {e}")  # Breaker open: breaker open for 59.8s more

# After 60s, HALF_OPEN allows one trial call
import time
time.sleep(60)
try:
    call_flaky_api("users")  # Trial call; success closes the breaker
except Exception:
    pass  # Fail re-opens
```

**Access breaker state:**

```python
@circuit_breaker(failure_threshold=5)
def my_tool():
    pass

print(my_tool.breaker.state)      # CircuitState.CLOSED
print(my_tool.breaker.failures)   # 0
print(my_tool.breaker.opened_at)  # None
```

**Gotchas:**

- Each decorated function has its own independent breaker. Decorating the same function twice creates two separate breakers.
- Thread-safe via internal locks, but state transitions are eventual — multiple threads may see different states briefly.

---

## `rate_limit`

Enforce a per-second call limit using a sliding window.

**Signature:**

```python
def rate_limit(
    *,
    per_second: float,
    raise_on_exceed: bool = True,
) -> Callable[[Callable], Callable]:
```

**Arguments:**

- `per_second`: Calls allowed per 1-second sliding window (> 0)
- `raise_on_exceed`: If `True`, raise `RateLimitExceeded` when limit is hit; if `False`, block (sleep) until the window clears

**Returns:** Decorator factory. Decorate a tool with `@rate_limit(...)`.

**Example — raise on exceed:**

```python
from codagent.tools import rate_limit, RateLimitExceeded

@rate_limit(per_second=2, raise_on_exceed=True)
def api_call(endpoint: str):
    return f"called {endpoint}"

# Two calls succeed
api_call("a")
api_call("b")

# Third call in same second fails
try:
    api_call("c")
except RateLimitExceeded as e:
    print(f"Rate limited: {e}")  # Rate limited: rate limit 2/s exceeded
```

**Example — block on exceed:**

```python
import time

@rate_limit(per_second=2, raise_on_exceed=False)
def api_call(endpoint: str):
    return f"called {endpoint}"

start = time.monotonic()
api_call("a")
api_call("b")
api_call("c")  # Sleeps until a call falls out of the 1s window
elapsed = time.monotonic() - start
print(f"Elapsed: {elapsed:.2f}s")  # ~1s
```

**Gotchas:**

- `per_second` can be fractional: `per_second=0.5` means 1 call per 2 seconds.
- Blocking mode (raise_on_exceed=False) sleeps on the main thread; avoid if latency is critical.
- Thread-safe via internal locks on the call queue.

---

## Stacking patterns

**Validation → Circuit → Rate limit:**

```python
from codagent.tools import validated_tool, circuit_breaker, rate_limit

def validate_search(kw):
    query = kw.get("query", "")
    if not query:
        raise ValueError("query required")
    return kw

@validated_tool(validate_search)
@circuit_breaker(failure_threshold=5, reset_after=60)
@rate_limit(per_second=10)
def search_api(query: str, limit: int = 10):
    pass
```

Order of stacking matters:

- `@validated_tool` outside (runs first): Catch bad args early before rate/circuit logic.
- `@circuit_breaker` middle: Avoid pile-up of requests if API is down.
- `@rate_limit` inside (runs last): Let throughput shaping happen close to the actual call.

**In LangChain agents:**

```python
from langchain.agents import tool
from codagent.tools import validated_tool, rate_limit

@validated_tool(my_validator)
@rate_limit(per_second=5)
@tool
def my_tool(query: str) -> str:
    """Do something"""
    pass
```

Validate before calling the underlying tool function.

---

## Exception types

**`CircuitBreakerOpen`**

Raised by a breaker in the OPEN state.

```python
from codagent.tools import CircuitBreakerOpen

try:
    breaker_tool()
except CircuitBreakerOpen as e:
    # e.args[0] is a message like "breaker open for 45.3s more"
    pass
```

**`RateLimitExceeded`**

Raised when `rate_limit(..., raise_on_exceed=True)` hits its limit.

```python
from codagent.tools import RateLimitExceeded

try:
    limited_tool()
except RateLimitExceeded as e:
    # e.args[0] is a message like "rate limit 10/s exceeded"
    pass
```

---

## See also

- [Nodes](nodes.md) — Wrap LLM calls with retry, timeout, cache
- [Production Hardening](../guides/production-hardening.md) — Stack nodes + tools + observability
