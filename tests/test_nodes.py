"""Tests for codagent.nodes wrappers."""

import time

import pytest

from codagent.nodes import (
    LoopDetected,
    NodeTimeout,
    parse_structured,
    with_cache,
    with_loop_guard,
    with_retry,
    with_timeout,
)


# -- with_retry -------------------------------------------------------------


def test_retry_succeeds_first_try():
    calls = []
    def node(state):
        calls.append(1)
        return {"ok": True}
    wrapped = with_retry(node, attempts=3)
    assert wrapped({}) == {"ok": True}
    assert len(calls) == 1


def test_retry_succeeds_after_failures():
    calls = []
    def node(state):
        calls.append(1)
        if len(calls) < 3:
            raise ValueError("transient")
        return {"ok": True}
    wrapped = with_retry(node, attempts=5, backoff=0.001)
    assert wrapped({})["ok"] is True
    assert len(calls) == 3


def test_retry_raises_last_error_after_exhaustion():
    def node(state):
        raise RuntimeError("always fails")
    wrapped = with_retry(node, attempts=2, backoff=0.001)
    with pytest.raises(RuntimeError):
        wrapped({})


def test_retry_only_catches_listed_exceptions():
    def node(state):
        raise KeyError("not in `on`")
    wrapped = with_retry(node, attempts=3, on=(ValueError,), backoff=0.001)
    with pytest.raises(KeyError):
        wrapped({})


def test_retry_invalid_attempts():
    with pytest.raises(ValueError):
        with_retry(lambda s: s, attempts=0)


# -- with_timeout -----------------------------------------------------------


def test_timeout_returns_when_under_budget():
    def fast(state): return {"ok": True}
    wrapped = with_timeout(fast, seconds=1.0)
    assert wrapped({}) == {"ok": True}


def test_timeout_raises_when_exceeded():
    def slow(state):
        time.sleep(0.5)
        return {}
    wrapped = with_timeout(slow, seconds=0.05)
    with pytest.raises(NodeTimeout):
        wrapped({})


def test_timeout_invalid_seconds():
    with pytest.raises(ValueError):
        with_timeout(lambda s: s, seconds=0)


# -- with_cache -------------------------------------------------------------


def test_cache_returns_same_result_for_same_key():
    calls = []
    def node(state):
        calls.append(1)
        return f"answer_{len(calls)}"
    wrapped = with_cache(node, key_fn=lambda s: s["q"])
    assert wrapped({"q": "x"}) == "answer_1"
    assert wrapped({"q": "x"}) == "answer_1"
    assert wrapped({"q": "y"}) == "answer_2"
    assert len(calls) == 2


def test_cache_ttl_expires():
    calls = []
    def node(state):
        calls.append(1)
        return len(calls)
    wrapped = with_cache(node, key_fn=lambda s: s["q"], ttl=0.05)
    assert wrapped({"q": "x"}) == 1
    time.sleep(0.1)
    assert wrapped({"q": "x"}) == 2


def test_cache_lru_eviction():
    calls = []
    def node(state):
        calls.append(1)
        return state["q"]
    wrapped = with_cache(node, key_fn=lambda s: s["q"], max_size=2)
    wrapped({"q": "a"})
    wrapped({"q": "b"})
    wrapped({"q": "c"})  # evicts "a"
    wrapped({"q": "a"})  # cache miss again
    assert len(calls) == 4


# -- parse_structured -------------------------------------------------------


def test_parse_structured_with_dict_output():
    @parse_structured(lambda d: {"normalized": d["raw"].upper()})
    def node(state): return {"raw": "hi"}
    assert node({}) == {"normalized": "HI"}


def test_parse_structured_with_json_string():
    @parse_structured(lambda d: d)
    def node(state): return '{"a": 1, "b": 2}'
    assert node({}) == {"a": 1, "b": 2}


# -- with_loop_guard --------------------------------------------------------


def test_loop_guard_allows_distinct_calls():
    calls = []
    def tool(*, query):
        calls.append(query)
        return query
    guarded = with_loop_guard(tool, window=5, max_repeats=3)
    for q in ("a", "b", "c", "d", "e"):
        guarded(query=q)
    assert calls == ["a", "b", "c", "d", "e"]


def test_loop_guard_allows_repeats_under_threshold():
    def tool(*, query):
        return query
    guarded = with_loop_guard(tool, window=5, max_repeats=3)
    guarded(query="x")
    guarded(query="x")
    guarded(query="x")  # 3rd identical, still allowed


def test_loop_guard_raises_on_excess_repeats():
    def tool(*, query):
        return query
    guarded = with_loop_guard(tool, window=10, max_repeats=3)
    guarded(query="x")
    guarded(query="x")
    guarded(query="x")
    with pytest.raises(LoopDetected):
        guarded(query="x")


def test_loop_guard_distinguishes_args():
    def tool(*, q):
        return q
    guarded = with_loop_guard(tool, window=10, max_repeats=2)
    guarded(q="a")
    guarded(q="a")
    guarded(q="b")  # different fingerprint, ok
    guarded(q="b")
    with pytest.raises(LoopDetected):
        guarded(q="a")  # 3rd "a" exceeds


def test_loop_guard_window_evicts_old_calls():
    def tool(*, q):
        return q
    guarded = with_loop_guard(tool, window=3, max_repeats=2)
    guarded(q="a")
    guarded(q="a")
    guarded(q="b")
    guarded(q="b")  # evicts first "a"
    # window now: [a, b, b]; one "a" remains, so a third "a" call is OK
    guarded(q="a")
    # now window: [b, b, a]; another "a" → 2 "a"s in window, still OK
    guarded(q="a")
    with pytest.raises(LoopDetected):
        guarded(q="a")


def test_loop_guard_custom_key_fn():
    def tool(payload):
        return payload["id"]
    guarded = with_loop_guard(
        tool,
        window=5,
        max_repeats=2,
        key_fn=lambda payload: payload["id"],
    )
    guarded({"id": 1, "x": "noise"})
    guarded({"id": 1, "x": "different"})
    with pytest.raises(LoopDetected):
        guarded({"id": 1, "x": "yet-other"})


def test_loop_guard_validates_params():
    with pytest.raises(ValueError):
        with_loop_guard(lambda: None, window=0, max_repeats=1)
    with pytest.raises(ValueError):
        with_loop_guard(lambda: None, window=1, max_repeats=0)


def test_loop_guard_handles_unhashable_args():
    def tool(state):
        return state.get("q", "")
    guarded = with_loop_guard(tool, window=10, max_repeats=2)
    guarded({"q": "x", "items": [1, 2, 3]})
    guarded({"q": "x", "items": [1, 2, 3]})
    with pytest.raises(LoopDetected):
        guarded({"q": "x", "items": [1, 2, 3]})
