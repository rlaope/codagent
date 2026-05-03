"""Phase 6 — RunMiddleware lifecycle hooks."""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("starlette")

from starlette.testclient import TestClient

from codagent.server import RunMiddleware, create_app
from codagent.server.runs import InMemoryRunRegistry


# -- Pure asyncio-level tests on middleware ---------------------------------


def _drive(coro):
    return asyncio.run(coro)


def test_before_run_can_mutate_body_before_llm_call():
    seen_bodies: list[dict] = []

    class _BodyTagger(RunMiddleware):
        async def before_run(self, run, body):
            body["_tagged"] = True

    async def capture(body):
        seen_bodies.append(dict(body))
        yield "ok"

    async def go():
        registry = InMemoryRunRegistry(middleware=[_BodyTagger()])
        run = registry.create_run(capture, {"prompt": "hi"})
        await run._task  # type: ignore[arg-type]

    _drive(go())
    assert seen_bodies[0]["_tagged"] is True
    assert seen_bodies[0]["prompt"] == "hi"


def test_after_event_sees_every_published_event_in_order():
    observed: list[str] = []

    class _Tap(RunMiddleware):
        async def after_event(self, run, event):
            observed.append(event.name)

    async def fake(_body):
        for tok in "abc":
            yield tok

    async def go():
        registry = InMemoryRunRegistry(middleware=[_Tap()])
        run = registry.create_run(fake, {})
        await run._task  # type: ignore[arg-type]

    _drive(go())
    assert observed == ["run.started", "token", "token", "token", "run.done"]


def test_after_run_fires_once_after_terminal_event():
    after_run_calls: list[str] = []

    class _Tracker(RunMiddleware):
        async def after_run(self, run):
            # Status reflects the terminal classification at this point.
            after_run_calls.append(run.status)

    async def fake(_body):
        yield "x"

    async def go():
        registry = InMemoryRunRegistry(middleware=[_Tracker()])
        run = registry.create_run(fake, {})
        await run._task  # type: ignore[arg-type]

    _drive(go())
    assert after_run_calls == ["completed"]


def test_before_run_raise_aborts_with_run_failed():
    class _Bouncer(RunMiddleware):
        async def before_run(self, run, body):
            raise RuntimeError("denied")

    llm_called: list[bool] = []

    async def fake(_body):
        llm_called.append(True)
        yield "x"

    async def go():
        registry = InMemoryRunRegistry(middleware=[_Bouncer()])
        run = registry.create_run(fake, {})
        await run._task  # type: ignore[arg-type]
        return run

    run = _drive(go())
    assert run.status == "failed"
    names = [e.name for e in run._events]  # type: ignore[attr-defined]
    assert "run.failed" in names
    # The LLM call was never made.
    assert llm_called == []


def test_after_event_error_does_not_break_run():
    class _Buggy(RunMiddleware):
        async def after_event(self, run, event):
            raise RuntimeError("boom")

    async def fake(_body):
        yield "ok"

    async def go():
        registry = InMemoryRunRegistry(middleware=[_Buggy()])
        run = registry.create_run(fake, {})
        await run._task  # type: ignore[arg-type]
        return run

    run = _drive(go())
    # Run completes naturally despite middleware errors.
    assert run.status == "completed"
    names = [e.name for e in run._events]  # type: ignore[attr-defined]
    assert "run.done" in names


def test_multiple_middleware_fire_in_registration_order():
    order: list[str] = []

    class _A(RunMiddleware):
        async def before_run(self, run, body):
            order.append("A.before")

        async def after_event(self, run, event):
            order.append(f"A.event:{event.name}")

        async def after_run(self, run):
            order.append("A.after")

    class _B(RunMiddleware):
        async def before_run(self, run, body):
            order.append("B.before")

        async def after_event(self, run, event):
            order.append(f"B.event:{event.name}")

        async def after_run(self, run):
            order.append("B.after")

    async def fake(_body):
        yield "x"

    async def go():
        registry = InMemoryRunRegistry(middleware=[_A(), _B()])
        run = registry.create_run(fake, {})
        await run._task  # type: ignore[arg-type]

    _drive(go())
    # Both `before` hooks fire before any event; both `after_event` fire
    # for each event in registration order; both `after_run` fire after
    # mark_done.
    assert order[0] == "A.before"
    assert order[1] == "B.before"
    # Last two entries are the after_run calls in registration order.
    assert order[-2:] == ["A.after", "B.after"]


# -- HTTP-level wiring -------------------------------------------------------


async def _two_token(_body):
    for tok in ["a", "b"]:
        yield tok


def test_create_app_accepts_middleware_kwarg():
    captured: list[str] = []

    class _Tap(RunMiddleware):
        async def after_event(self, run, event):
            captured.append(event.name)

    app = create_app(llm_call=_two_token, middleware=[_Tap()])
    with TestClient(app) as client:
        resp = client.post("/v1/runs", json={})
        run_id = resp.json()["run_id"]
        with client.stream("GET", f"/v1/runs/{run_id}/events") as stream:
            b"".join(stream.iter_bytes())

    # Started + 2 tokens + done.
    assert captured == ["run.started", "token", "token", "run.done"]
