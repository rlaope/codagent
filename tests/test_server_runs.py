"""Phase 2 — run lifecycle and replayable event stream tests."""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("starlette")

from codagent.server import create_app
from codagent.server.runs import AgentRun, InMemoryRunRegistry, run_task


# -- Pure asyncio-level tests on AgentRun (no HTTP) -----------------------


def _drive(coro):
    return asyncio.run(coro)


def test_subscribe_replays_history_after_completion():
    async def fake(_body):
        for tok in "abc":
            yield tok

    async def go():
        registry = InMemoryRunRegistry()
        run = registry.create_run(fake, {})
        # Wait for the run to finish.
        await run._task  # type: ignore[arg-type]

        events = [e async for e in run.subscribe()]
        return events

    events = _drive(go())
    names = [e.name for e in events]
    assert names == ["run.started", "token", "token", "token", "run.done"]
    assert [e.id for e in events] == [1, 2, 3, 4, 5]


def test_subscribe_with_last_event_id_skips_already_seen():
    async def fake(_body):
        for tok in "abcde":
            yield tok

    async def go():
        registry = InMemoryRunRegistry()
        run = registry.create_run(fake, {})
        await run._task  # type: ignore[arg-type]

        events = [e async for e in run.subscribe(last_event_id=3)]
        return events

    events = _drive(go())
    # events 1,2,3 (run.started, token, token) skipped; 4,5,6,7 remain
    # token, token, token, run.done
    assert [e.id for e in events] == [4, 5, 6, 7]
    assert events[-1].name == "run.done"


def test_two_concurrent_subscribers_see_same_event_sequence():
    async def fake(_body):
        # Sleeps let subscribers attach before the first token.
        await asyncio.sleep(0)
        for tok in "abc":
            await asyncio.sleep(0)
            yield tok

    async def go():
        registry = InMemoryRunRegistry()
        run = registry.create_run(fake, {})

        async def collect():
            return [e async for e in run.subscribe()]

        sub1, sub2 = await asyncio.gather(collect(), collect())
        await run._task  # type: ignore[arg-type]
        return sub1, sub2

    sub1, sub2 = _drive(go())
    assert [e.name for e in sub1] == [e.name for e in sub2]
    # Both should see the full lifecycle (5 events: started + 3 token + done).
    assert len(sub1) == 5
    assert sub1[-1].name == "run.done"


def test_explicit_cancel_propagates_finally_in_upstream_generator():
    upstream_finally_ran: list[bool] = []
    tokens_yielded: list[str] = []

    async def slow_fake(_body):
        try:
            for tok in "abcdef":
                tokens_yielded.append(tok)
                # Yield control so cancel can land between iterations.
                await asyncio.sleep(0)
                yield tok
        finally:
            upstream_finally_ran.append(True)

    async def go():
        registry = InMemoryRunRegistry()
        run = registry.create_run(slow_fake, {})

        async def cancel_after_two():
            # Wait for the first two tokens to be published, then cancel.
            while True:
                names = [e.name for e in run._events]  # type: ignore[attr-defined]
                if names.count("token") >= 2:
                    run.request_cancel()
                    return
                await asyncio.sleep(0)

        await asyncio.gather(cancel_after_two(), run._task)  # type: ignore[arg-type]
        return run

    run = _drive(go())
    assert run.status == "cancelled"
    terminal = run._events[-1]  # type: ignore[attr-defined]
    assert terminal.name == "run.cancelled"
    # Upstream's finally block ran — that is the cancel-propagation property.
    assert upstream_finally_ran == [True]
    # We didn't iterate all six tokens.
    assert len(tokens_yielded) <= 4


def test_run_failure_emits_run_failed():
    async def boom(_body):
        yield "ok"
        raise RuntimeError("kaboom")

    async def go():
        registry = InMemoryRunRegistry()
        run = registry.create_run(boom, {})
        await run._task  # type: ignore[arg-type]
        return run

    run = _drive(go())
    assert run.status == "failed"
    assert run._events[-1].name == "run.failed"  # type: ignore[attr-defined]
    assert "kaboom" in run._events[-1].data["error"]  # type: ignore[attr-defined]


# -- HTTP-level tests --------------------------------------------------------


def _short_run_app():
    async def fake(body):
        for tok in body.get("prompt", "a b c").split():
            yield tok

    return create_app(llm_call=fake)


def test_http_full_run_lifecycle_via_events_endpoint():
    from starlette.testclient import TestClient

    client = TestClient(_short_run_app())
    resp = client.post("/v1/runs", json={"prompt": "one two three"})
    assert resp.status_code == 201
    run_id = resp.json()["run_id"]

    with client.stream("GET", f"/v1/runs/{run_id}/events") as stream:
        body = b"".join(stream.iter_bytes()).decode()

    assert body.count("event: token") == 3
    assert "event: run.started" in body
    assert "event: run.done" in body
    # SSE id field is present on each event for Last-Event-Id support.
    assert "id: 1" in body and "id: 5" in body


def test_http_get_run_snapshot_evolves():
    from starlette.testclient import TestClient

    client = TestClient(_short_run_app())
    resp = client.post("/v1/runs", json={"prompt": "a b"})
    run_id = resp.json()["run_id"]

    # Drive the run to completion by consuming the event stream.
    with client.stream("GET", f"/v1/runs/{run_id}/events") as stream:
        b"".join(stream.iter_bytes())

    snap = client.get(f"/v1/runs/{run_id}").json()
    assert snap["run_id"] == run_id
    assert snap["status"] == "completed"
    assert snap["finished_at"] is not None


def test_http_last_event_id_replay_skips_seen_events():
    from starlette.testclient import TestClient

    client = TestClient(_short_run_app())
    resp = client.post("/v1/runs", json={"prompt": "alpha beta gamma delta"})
    run_id = resp.json()["run_id"]

    # Consume once to push the run to completion.
    with client.stream("GET", f"/v1/runs/{run_id}/events") as stream:
        b"".join(stream.iter_bytes())

    # Reconnect with Last-Event-Id: 2 — should miss run.started + first token.
    with client.stream(
        "GET",
        f"/v1/runs/{run_id}/events",
        headers={"Last-Event-Id": "2"},
    ) as stream:
        body = b"".join(stream.iter_bytes()).decode()

    assert "event: run.started" not in body
    # Original ids: 1=started, 2=alpha, 3=beta, 4=gamma, 5=delta, 6=done.
    # With Last-Event-Id: 2 we should see ids 3..6 → 3 tokens + done.
    assert body.count("event: token") == 3
    assert "event: run.done" in body


def test_http_cancel_endpoint_terminates_run_with_cancelled_event():
    from starlette.testclient import TestClient

    upstream_cleanup: list[bool] = []

    async def slow(_body):
        try:
            for tok in "abcdef":
                await asyncio.sleep(0)
                yield tok
        finally:
            upstream_cleanup.append(True)

    client = TestClient(create_app(llm_call=slow))
    resp = client.post("/v1/runs", json={})
    run_id = resp.json()["run_id"]

    cancel_resp = client.post(f"/v1/runs/{run_id}/cancel")
    assert cancel_resp.status_code == 200
    # By the time cancel responds, the runner has already terminated,
    # so the status field reflects the final state.
    assert cancel_resp.json()["status"] == "cancelled"

    with client.stream("GET", f"/v1/runs/{run_id}/events") as stream:
        body = b"".join(stream.iter_bytes()).decode()

    assert "event: run.cancelled" in body
    assert "event: run.done" not in body
    assert upstream_cleanup == [True]

    snap = client.get(f"/v1/runs/{run_id}").json()
    assert snap["status"] == "cancelled"


def test_http_cancel_unknown_run_returns_404():
    from starlette.testclient import TestClient

    client = TestClient(_short_run_app())
    assert client.post("/v1/runs/missing/cancel").status_code == 404
    assert client.get("/v1/runs/missing/events").status_code == 404
