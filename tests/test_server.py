"""Tests for codagent.server.

Skipped entirely when the 'server' extra is not installed.
"""

from __future__ import annotations

import asyncio

import pytest

starlette = pytest.importorskip("starlette")

from codagent.server import create_app
from codagent.server.app import _run_stream


# -- Pure async-generator level (no HTTP) -----------------------------------


def _drive(coro):
    return asyncio.run(coro)


def test_run_stream_emits_started_tokens_done():
    async def fake_llm(_body):
        for tok in ["hello", "world"]:
            yield tok

    async def never_disconnected():
        return False

    async def collect():
        return [ev async for ev in _run_stream(fake_llm, {}, never_disconnected)]

    events = _drive(collect())
    text = "".join(events)
    assert "event: run.started" in text
    assert text.count("event: token") == 2
    assert "hello" in text and "world" in text
    assert "event: run.done" in text


def test_run_stream_cancels_on_disconnect_and_closes_llm_generator():
    seen = []
    cleanup = []

    async def fake_llm(_body):
        try:
            for tok in "abcdef":
                seen.append(tok)
                yield tok
        finally:
            cleanup.append(True)

    calls = [0]

    async def is_disconnected():
        calls[0] += 1
        # First two checks: still connected. After that: disconnected.
        return calls[0] > 2

    async def collect():
        return [ev async for ev in _run_stream(fake_llm, {}, is_disconnected)]

    events = _drive(collect())
    text = "".join(events)

    assert "event: run.started" in text
    assert "event: run.cancelled" in text
    assert "event: run.done" not in text
    # We stopped early — the generator did not iterate all six tokens.
    assert len(seen) <= 3
    # finally block ran → upstream cleanup happened.
    assert cleanup == [True]


# -- HTTP smoke test --------------------------------------------------------


def test_post_runs_streams_sse_events():
    from starlette.testclient import TestClient

    async def fake_llm(body):
        for tok in body["prompt"].split():
            yield tok

    client = TestClient(create_app(llm_call=fake_llm))
    with client.stream(
        "POST", "/v1/runs", json={"prompt": "one two three"}
    ) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        body = b"".join(resp.iter_bytes()).decode()

    assert "event: run.started" in body
    assert body.count("event: token") == 3
    assert "one" in body and "two" in body and "three" in body
    assert "event: run.done" in body


def test_post_runs_rejects_non_json():
    from starlette.testclient import TestClient

    async def fake_llm(_body):
        yield "x"

    client = TestClient(create_app(llm_call=fake_llm))
    resp = client.post("/v1/runs", content="not json", headers={"content-type": "text/plain"})
    assert resp.status_code == 400


def test_healthz():
    from starlette.testclient import TestClient

    async def fake_llm(_body):
        yield "x"

    client = TestClient(create_app(llm_call=fake_llm))
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
