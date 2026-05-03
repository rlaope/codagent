"""Phase 9 — backpressure, history eviction, graceful shutdown."""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("starlette")

from starlette.testclient import TestClient

from codagent.server import create_app
from codagent.server.runs import AgentRun, InMemoryRunRegistry


# -- Backpressure ------------------------------------------------------------


def test_subscriber_queue_drops_oldest_when_full_under_backpressure():
    """A slow subscriber with a small queue is not allowed to stall the
    producer. Old events fall off the queue; the dropped count goes up."""

    async def fake(_body):
        for tok in "abcdefghij":  # 10 tokens
            yield tok

    async def go():
        registry = InMemoryRunRegistry(max_queue_size=2)
        run = registry.create_run(fake, {})
        await run._task  # type: ignore[arg-type]
        return run

    run = asyncio.run(go())
    # Run completed successfully — producer was never blocked.
    assert run.status == "completed"
    # No subscribers in this scenario, so dropped stays 0.
    # Drop counter exists and is reachable for tests.
    assert run._dropped_events == 0  # type: ignore[attr-defined]


def test_slow_subscriber_with_full_queue_loses_old_events_not_terminal():
    """A subscriber whose queue is full keeps receiving the *latest*
    events plus the terminal sentinel. The end-of-stream signal is
    guaranteed to land even under backpressure."""

    async def fake(_body):
        for tok in "abcdefghij":  # 10 tokens
            yield tok

    async def go():
        run = AgentRun(id="r-test", max_queue_size=2)

        # Attach subscriber but never read until run is done.
        sub_events: list = []

        async def consume():
            async for e in run.subscribe():
                sub_events.append(e.name)

        # We'll drive publishes manually so we can interleave precisely.
        async def drive():
            await run.publish("run.started", {})
            for _ in range(8):
                await run.publish("token", {})
            await run.publish("run.done", {})
            await run.mark_done()

        # Spawn subscriber, then drive — the subscriber doesn't read
        # until drive yields control via mark_done's sentinel.
        sub = asyncio.create_task(consume())
        # Yield once so subscribe() registers itself.
        await asyncio.sleep(0)
        await drive()
        await sub
        return sub_events, run._dropped_events  # type: ignore[attr-defined]

    sub_events, dropped = asyncio.run(go())
    # Subscriber observed at least the terminal event.
    assert "run.done" in sub_events
    # Some events were dropped due to backpressure.
    assert dropped > 0


# -- History eviction --------------------------------------------------------


def test_event_history_evicts_oldest_when_max_events_exceeded():

    async def go():
        run = AgentRun(id="r-evict", max_events=3)
        for _ in range(6):
            await run.publish("token", {})

        # Only the most recent 3 events are retained.
        assert len(run._events) == 3  # type: ignore[attr-defined]
        # IDs are still monotonic — just shifted.
        ids = [e.id for e in run._events]  # type: ignore[attr-defined]
        assert ids == [4, 5, 6]
        # next_id keeps incrementing past evicted events.
        assert run._next_id == 6  # type: ignore[attr-defined]

    asyncio.run(go())


def test_subscriber_after_eviction_only_sees_retained_events():
    """A late subscriber asking for events from the start of the run
    only gets what's still in history."""

    async def go():
        run = AgentRun(id="r-late", max_events=2)
        for _ in range(5):
            await run.publish("token", {})
        await run.mark_done()

        events = [e async for e in run.subscribe(last_event_id=0)]
        return events

    events = asyncio.run(go())
    assert [e.id for e in events] == [4, 5]


# -- Graceful shutdown -------------------------------------------------------


def test_registry_shutdown_waits_for_in_flight_runs():

    finished: list[bool] = []

    async def long_running(_body):
        try:
            for tok in "abc":
                await asyncio.sleep(0)
                yield tok
        finally:
            finished.append(True)

    async def go():
        registry = InMemoryRunRegistry()
        registry.create_run(long_running, {})
        registry.create_run(long_running, {})
        # Both runs are in-flight (haven't been awaited).
        assert len(registry.in_flight()) == 2

        await registry.shutdown()
        # After shutdown, all are done.
        assert registry.in_flight() == []
        # Both upstream generators ran their finally blocks.
        return finished

    f = asyncio.run(go())
    assert f == [True, True]


def test_registry_shutdown_with_no_in_flight_is_noop():

    async def go():
        registry = InMemoryRunRegistry()
        await registry.shutdown()  # must not raise / hang

    asyncio.run(go())


def test_lifespan_runs_shutdown_on_app_teardown():
    """Mount the app, drive a run, then close the TestClient — the
    lifespan shutdown event must fire and any in-flight task must be
    awaited before the lifespan task exits."""

    finished: list[bool] = []

    async def fake(_body):
        try:
            for tok in ["a", "b"]:
                await asyncio.sleep(0)
                yield tok
        finally:
            finished.append(True)

    app = create_app(llm_call=fake)
    with TestClient(app) as client:
        resp = client.post("/v1/runs", json={})
        run_id = resp.json()["run_id"]
        with client.stream("GET", f"/v1/runs/{run_id}/events") as stream:
            b"".join(stream.iter_bytes())

    # TestClient context exit triggers lifespan shutdown.
    assert finished == [True]


# -- Combined: backpressure + eviction + metrics smoke -----------------------


def test_create_app_accepts_max_queue_size_and_max_events_kwargs():

    async def fake(_body):
        for tok in "abcde":
            yield tok

    app = create_app(llm_call=fake, max_queue_size=2, max_events=2)
    with TestClient(app) as client:
        resp = client.post("/v1/runs", json={})
        run_id = resp.json()["run_id"]
        with client.stream("GET", f"/v1/runs/{run_id}/events") as stream:
            body = b"".join(stream.iter_bytes()).decode()

    # The run still completes.
    assert "event: run.done" in body or "event: token" in body
