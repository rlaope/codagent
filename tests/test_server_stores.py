"""Phase 7 — persistence backend protocols (RunStore, BudgetStore)."""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("starlette")

from starlette.testclient import TestClient

from codagent.server import (
    BudgetStore,
    InMemoryBudgetStore,
    InMemoryRunStore,
    RunStore,
    create_app,
)
from codagent.server.budgets import BudgetConfig, BudgetGate
from codagent.server.runs import InMemoryRunRegistry


# -- BudgetStore ------------------------------------------------------------


def test_in_memory_budget_store_zero_init():
    store = InMemoryBudgetStore()
    s = store.get("alice")
    assert s == {"input_tokens": 0, "output_tokens": 0, "usd": 0.0, "steps": 0}


def test_in_memory_budget_store_set_then_get():
    store = InMemoryBudgetStore()
    store.set(
        "bob",
        {"input_tokens": 5, "output_tokens": 10, "usd": 0.25, "steps": 10},
    )
    assert store.get("bob")["output_tokens"] == 10
    # Get returns a copy: caller mutations must not leak into store.
    snap = store.get("bob")
    snap["output_tokens"] = 999
    assert store.get("bob")["output_tokens"] == 10


def test_budget_gate_uses_injected_budget_store():

    class _CountingStore:
        def __init__(self):
            self.gets = 0
            self.sets = 0
            self._inner = InMemoryBudgetStore()

        def get(self, user_id):
            self.gets += 1
            return self._inner.get(user_id)

        def set(self, user_id, state):
            self.sets += 1
            self._inner.set(user_id, state)

    store = _CountingStore()
    gate = BudgetGate(BudgetConfig(output_tokens=5), store=store)
    gate.record_token("alice", "output", 1)
    gate.record_token("alice", "output", 1)
    gate.check("alice")
    assert store.sets == 2  # one per record_token
    assert store.gets >= 3  # two records + at least one check


def test_custom_budget_store_persists_across_gate_instances():

    backing = InMemoryBudgetStore()
    gate_a = BudgetGate(BudgetConfig(output_tokens=3), store=backing)
    gate_a.record_token("alice", "output", 2)

    # New gate instance, same store — sees the prior usage.
    gate_b = BudgetGate(BudgetConfig(output_tokens=3), store=backing)
    s = gate_b.state_of("alice")
    assert s["output_tokens"] == 2

    gate_b.record_token("alice", "output", 1)
    v = gate_b.check("alice")
    assert v is not None
    assert v["limit"] == "output_tokens"


# -- RunStore ---------------------------------------------------------------


def test_in_memory_run_store_save_and_load_snapshot():
    async def go():
        store = InMemoryRunStore()
        snap = {"run_id": "r1", "status": "running", "created_at": 1.0, "finished_at": None}
        await store.save_snapshot(snap)
        loaded = await store.load_snapshot("r1")
        assert loaded == snap
        assert await store.load_snapshot("nope") is None

    asyncio.run(go())


def test_run_store_records_full_event_history_via_registry():

    async def fake(_body):
        for tok in "abc":
            yield tok

    async def go():
        store = InMemoryRunStore()
        registry = InMemoryRunRegistry(run_store=store)
        run = registry.create_run(fake, {})
        await run._task  # type: ignore[arg-type]

        events = await store.get_events(run.id)
        return run, events

    run, events = asyncio.run(go())
    names = [e.name for e in events]
    assert names == ["run.started", "token", "token", "token", "run.done"]
    assert [e.id for e in events] == [1, 2, 3, 4, 5]


def test_run_store_after_id_filters_seen_events():

    async def fake(_body):
        for tok in "abc":
            yield tok

    async def go():
        store = InMemoryRunStore()
        registry = InMemoryRunRegistry(run_store=store)
        run = registry.create_run(fake, {})
        await run._task  # type: ignore[arg-type]
        return run.id, await store.get_events(run.id, after_id=2)

    run_id, events = asyncio.run(go())
    assert [e.id for e in events] == [3, 4, 5]


def test_run_store_snapshot_reflects_terminal_status():

    async def fake(_body):
        yield "ok"

    async def go():
        store = InMemoryRunStore()
        registry = InMemoryRunRegistry(run_store=store)
        run = registry.create_run(fake, {})
        await run._task  # type: ignore[arg-type]
        return run.id, await store.load_snapshot(run.id)

    run_id, snap = asyncio.run(go())
    assert snap["status"] == "completed"
    assert snap["finished_at"] is not None


def test_custom_run_store_protocol_implementation_is_honoured():

    captured: list[tuple[str, str]] = []

    class _SpyStore:
        async def save_snapshot(self, snapshot):
            captured.append(("snapshot", snapshot["status"]))

        async def load_snapshot(self, run_id):
            return None

        async def append_event(self, run_id, event):
            captured.append(("event", event.name))

        async def get_events(self, run_id, after_id=0):
            return []

    async def fake(_body):
        yield "x"

    async def go():
        registry = InMemoryRunRegistry(run_store=_SpyStore())
        run = registry.create_run(fake, {})
        await run._task  # type: ignore[arg-type]

    asyncio.run(go())
    # Snapshot saved on before_run (queued), each event mirrored, snapshot
    # saved again on after_run (terminal).
    kinds = [c[0] for c in captured]
    assert kinds[0] == "snapshot"
    assert kinds[-1] == "snapshot"
    # Three events in between: run.started, token, run.done.
    event_names = [c[1] for c in captured if c[0] == "event"]
    assert event_names == ["run.started", "token", "run.done"]


# -- HTTP-level wiring -------------------------------------------------------


async def _two_token(_body):
    for tok in ["a", "b"]:
        yield tok


def test_create_app_accepts_run_store_kwarg_and_records_events():

    store = InMemoryRunStore()
    app = create_app(llm_call=_two_token, run_store=store)
    with TestClient(app) as client:
        resp = client.post("/v1/runs", json={})
        run_id = resp.json()["run_id"]
        with client.stream("GET", f"/v1/runs/{run_id}/events") as stream:
            b"".join(stream.iter_bytes())

    async def fetch():
        return await store.get_events(run_id), await store.load_snapshot(run_id)

    events, snap = asyncio.run(fetch())
    names = [e.name for e in events]
    assert names == ["run.started", "token", "token", "run.done"]
    assert snap["status"] == "completed"


def test_create_app_accepts_budget_store_kwarg_and_persists_state():
    """Budget state survives across separate app instances when they share
    a store. (Production scenario: app restarts but Redis store retains
    counters.)"""

    backing = InMemoryBudgetStore()

    # First app instance: alice burns through her budget.
    app1 = create_app(
        llm_call=_two_token,
        budget=BudgetConfig(output_tokens=2),
        budget_store=backing,
    )
    with TestClient(app1) as client:
        resp = client.post(
            "/v1/runs", json={}, headers={"x-codagent-user": "alice"}
        )
        run_id = resp.json()["run_id"]
        with client.stream("GET", f"/v1/runs/{run_id}/events") as stream:
            b"".join(stream.iter_bytes())

    # Second app instance with the same backing store: alice is
    # pre-empted on first request.
    app2 = create_app(
        llm_call=_two_token,
        budget=BudgetConfig(output_tokens=2),
        budget_store=backing,
    )
    with TestClient(app2) as client:
        resp = client.post(
            "/v1/runs", json={}, headers={"x-codagent-user": "alice"}
        )
        run_id = resp.json()["run_id"]
        with client.stream("GET", f"/v1/runs/{run_id}/events") as stream:
            body = b"".join(stream.iter_bytes()).decode()

    # No tokens were emitted on the second app — store-backed
    # pre-emption fired.
    assert "event: run.budget_exceeded" in body
    assert body.count("event: token") == 0
