"""Tests for codagent.tools decorators."""

import time

import pytest

from codagent.tools import (
    CircuitBreakerOpen,
    RateLimitExceeded,
    circuit_breaker,
    rate_limit,
    validated_tool,
)


# -- validated_tool ---------------------------------------------------------


def test_validated_tool_passes_through_valid_args():
    def validator(kw):
        if "query" not in kw or not kw["query"]:
            raise ValueError("query required")
        return kw
    @validated_tool(validator)
    def tool(query, limit=5):
        return f"results for {query} (limit {limit})"
    assert tool(query="x") == "results for x (limit 5)"


def test_validated_tool_rejects_invalid_args():
    def validator(kw):
        if not kw.get("query"):
            raise ValueError("missing query")
        return kw
    @validated_tool(validator)
    def tool(query): return query
    with pytest.raises(ValueError):
        tool(query="")


def test_validated_tool_validator_must_return_dict():
    @validated_tool(lambda kw: "not a dict")
    def tool(**kw): return kw
    with pytest.raises(TypeError):
        tool(x=1)


# -- circuit_breaker --------------------------------------------------------


def test_circuit_closes_on_success():
    @circuit_breaker(failure_threshold=2, reset_after=0.1)
    def t(): return "ok"
    assert t() == "ok"
    assert t() == "ok"


def test_circuit_opens_after_threshold():
    @circuit_breaker(failure_threshold=2, reset_after=0.05)
    def t():
        raise RuntimeError("boom")
    with pytest.raises(RuntimeError): t()
    with pytest.raises(RuntimeError): t()
    with pytest.raises(CircuitBreakerOpen):
        t()


def test_circuit_half_open_recovers():
    state = {"fail": True}
    @circuit_breaker(failure_threshold=1, reset_after=0.05)
    def t():
        if state["fail"]:
            raise RuntimeError("boom")
        return "ok"
    with pytest.raises(RuntimeError): t()
    with pytest.raises(CircuitBreakerOpen): t()  # immediate fast-fail
    time.sleep(0.06)
    state["fail"] = False
    assert t() == "ok"  # half-open trial succeeds, breaker closes


def test_circuit_invalid_args():
    with pytest.raises(ValueError):
        circuit_breaker(failure_threshold=0)
    with pytest.raises(ValueError):
        circuit_breaker(reset_after=0)


# -- rate_limit -------------------------------------------------------------


def test_rate_limit_under_limit_passes():
    @rate_limit(per_second=10)
    def t(): return "ok"
    for _ in range(5):
        assert t() == "ok"


def test_rate_limit_raises_at_limit():
    @rate_limit(per_second=2, raise_on_exceed=True)
    def t(): return "ok"
    t()
    t()
    with pytest.raises(RateLimitExceeded):
        t()


def test_rate_limit_blocks_when_not_raising():
    @rate_limit(per_second=2, raise_on_exceed=False)
    def t(): return "ok"
    t()
    t()
    start = time.monotonic()
    t()  # should block roughly until window slides
    elapsed = time.monotonic() - start
    assert elapsed >= 0.5  # ~1s window minus first call age


def test_rate_limit_invalid_args():
    with pytest.raises(ValueError):
        rate_limit(per_second=0)
