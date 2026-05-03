"""Phase 4 — sessions and reconnect-and-replay across runs."""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("starlette")

from starlette.testclient import TestClient

from codagent.server import create_app
from codagent.server.sessions import InMemorySessionStore


# -- Pure session-store level ------------------------------------------------


def test_in_memory_session_store_create_and_list():
    store = InMemorySessionStore()
    sid = store.create_session()
    assert isinstance(sid, str) and len(sid) > 0
    assert store.get_session(sid)["session_id"] == sid
    assert store.list_runs(sid) == []

    store.attach_run(sid, "run-a")
    store.attach_run(sid, "run-b")
    assert store.list_runs(sid) == ["run-a", "run-b"]


def test_in_memory_session_store_unknown_session():
    store = InMemorySessionStore()
    assert store.get_session("nope") is None
    assert store.list_runs("nope") == []


# -- HTTP wiring -------------------------------------------------------------


async def _two_token_fake(_body):
    for tok in ["a", "b"]:
        yield tok


def test_post_sessions_returns_session_id():

    with TestClient(create_app(llm_call=_two_token_fake)) as client:
        resp = client.post("/v1/sessions")
        assert resp.status_code == 201
        body = resp.json()
        assert "session_id" in body
        assert isinstance(body["session_id"], str)


def test_run_with_session_id_appears_in_list_runs():

    with TestClient(create_app(llm_call=_two_token_fake)) as client:
        sid = client.post("/v1/sessions").json()["session_id"]
        run_a = client.post(
            "/v1/runs", json={"prompt": "first", "session_id": sid}
        ).json()["run_id"]
        run_b = client.post(
            "/v1/runs", json={"prompt": "second", "session_id": sid}
        ).json()["run_id"]

        listing = client.get(f"/v1/sessions/{sid}/runs").json()

    assert listing["session_id"] == sid
    assert listing["runs"] == [run_a, run_b]


def test_run_without_session_id_is_not_tracked():

    with TestClient(create_app(llm_call=_two_token_fake)) as client:
        sid = client.post("/v1/sessions").json()["session_id"]
        # Run created with no session_id
        client.post("/v1/runs", json={"prompt": "lone"}).json()
        listing = client.get(f"/v1/sessions/{sid}/runs").json()

    assert listing["runs"] == []


def test_list_runs_for_unknown_session_is_404():

    with TestClient(create_app(llm_call=_two_token_fake)) as client:
        resp = client.get("/v1/sessions/does-not-exist/runs")
        assert resp.status_code == 404


def test_reconnect_after_post_caller_gone_replays_full_event_sequence():
    """The run must outlive the POST /v1/runs call. A subscriber that
    attaches AFTER the POST has returned (and after the run has even
    completed) must still be able to read the full event sequence —
    that is the property a reconnecting client depends on."""

    async def fake(body):
        for tok in body.get("prompt", "x").split():
            yield tok

    app = create_app(llm_call=fake)

    with TestClient(app) as client:
        sid = client.post("/v1/sessions").json()["session_id"]
        run_id = client.post(
            "/v1/runs", json={"prompt": "alpha beta gamma", "session_id": sid}
        ).json()["run_id"]

        # Drive the run to completion via one subscriber.
        with client.stream("GET", f"/v1/runs/{run_id}/events") as s:
            first = b"".join(s.iter_bytes()).decode()
        assert "event: run.done" in first

        # The original POST caller is "gone" by definition (we got the
        # response). Reconnect with Last-Event-Id: 0 should replay all
        # events because AgentRun history is retained.
        with client.stream(
            "GET",
            f"/v1/runs/{run_id}/events",
            headers={"Last-Event-Id": "0"},
        ) as s:
            replay = b"".join(s.iter_bytes()).decode()

    assert "event: run.started" in replay
    assert replay.count("event: token") == 3
    assert "event: run.done" in replay


def test_session_id_is_not_passed_through_to_llm_call_body():
    """session_id is server metadata; it must not leak into the LLM
    call's body."""

    seen_bodies: list[dict] = []

    async def capture(body):
        seen_bodies.append(dict(body))
        yield "ok"

    with TestClient(create_app(llm_call=capture)) as client:
        sid = client.post("/v1/sessions").json()["session_id"]
        run_id = client.post(
            "/v1/runs", json={"prompt": "x", "session_id": sid}
        ).json()["run_id"]
        with client.stream("GET", f"/v1/runs/{run_id}/events") as s:
            b"".join(s.iter_bytes())

    assert seen_bodies[0].get("prompt") == "x"
    assert "session_id" not in seen_bodies[0]


def test_create_app_accepts_custom_session_store():
    """Custom SessionStore implementations are honoured."""

    class _CountingStore(InMemorySessionStore):
        def __init__(self):
            super().__init__()
            self.attach_calls = 0

        def attach_run(self, session_id, run_id):
            self.attach_calls += 1
            super().attach_run(session_id, run_id)

    store = _CountingStore()
    with TestClient(create_app(llm_call=_two_token_fake, session_store=store)) as client:
        sid = client.post("/v1/sessions").json()["session_id"]
        client.post("/v1/runs", json={"prompt": "x", "session_id": sid})
        client.post("/v1/runs", json={"prompt": "y", "session_id": sid})

    assert store.attach_calls == 2
