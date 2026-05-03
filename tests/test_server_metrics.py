"""Phase 9 — metrics."""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("starlette")

from starlette.testclient import TestClient

from codagent.server import InMemoryMetrics, create_app
from codagent.server.runs import InMemoryRunRegistry


# -- InMemoryMetrics primitives ---------------------------------------------


def test_in_memory_metrics_inc_and_counter():
    m = InMemoryMetrics()
    m.inc("a")
    m.inc("a", 4)
    assert m.counter("a") == 5
    assert m.counter("b") == 0


def test_in_memory_metrics_tags_are_independent_dimensions():
    m = InMemoryMetrics()
    m.inc("hits", route="/a")
    m.inc("hits", route="/b")
    m.inc("hits", route="/a", method="GET")
    assert m.counter("hits", route="/a") == 1
    assert m.counter("hits", route="/b") == 1
    assert m.counter("hits", route="/a", method="GET") == 1


def test_in_memory_metrics_observe():
    m = InMemoryMetrics()
    m.observe("latency_ms", 10.0)
    m.observe("latency_ms", 25.0)
    assert m.observations("latency_ms") == [10.0, 25.0]


# -- _MetricsMiddleware via registry ----------------------------------------


def test_registry_metrics_records_run_started_and_completed():

    async def fake(_body):
        for tok in "abc":
            yield tok

    async def go():
        m = InMemoryMetrics()
        registry = InMemoryRunRegistry(metrics=m)
        run = registry.create_run(fake, {})
        await run._task  # type: ignore[arg-type]
        return m

    m = asyncio.run(go())
    assert m.counter("codagent.runs.started") == 1
    assert m.counter("codagent.runs.completed") == 1
    assert m.counter("codagent.tokens.emitted") == 3
    assert m.counter("codagent.runs.failed") == 0


def test_registry_metrics_records_failed_run():

    async def boom(_body):
        yield "ok"
        raise RuntimeError("nope")

    async def go():
        m = InMemoryMetrics()
        registry = InMemoryRunRegistry(metrics=m)
        run = registry.create_run(boom, {})
        await run._task  # type: ignore[arg-type]
        return m

    m = asyncio.run(go())
    assert m.counter("codagent.runs.failed") == 1
    assert m.counter("codagent.runs.completed") == 0


def test_registry_metrics_records_cancelled_run():

    async def slow(_body):
        try:
            for tok in "abcdef":
                await asyncio.sleep(0)
                yield tok
        finally:
            pass

    async def go():
        m = InMemoryMetrics()
        registry = InMemoryRunRegistry(metrics=m)
        run = registry.create_run(slow, {})

        async def cancel_after_two():
            while [e.name for e in run._events].count("token") < 2:  # type: ignore[attr-defined]
                await asyncio.sleep(0)
            run.request_cancel()

        await asyncio.gather(cancel_after_two(), run._task)  # type: ignore[arg-type]
        return m

    m = asyncio.run(go())
    assert m.counter("codagent.runs.cancelled") == 1
    assert m.counter("codagent.runs.completed") == 0


def test_create_app_accepts_metrics_kwarg():

    async def fake(_body):
        for tok in ["a", "b"]:
            yield tok

    m = InMemoryMetrics()
    app = create_app(llm_call=fake, metrics=m)
    with TestClient(app) as client:
        resp = client.post("/v1/runs", json={})
        run_id = resp.json()["run_id"]
        with client.stream("GET", f"/v1/runs/{run_id}/events") as stream:
            b"".join(stream.iter_bytes())

    assert m.counter("codagent.runs.started") == 1
    assert m.counter("codagent.runs.completed") == 1
    assert m.counter("codagent.tokens.emitted") == 2
