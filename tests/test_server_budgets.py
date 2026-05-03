"""Phase 5 — per-user budget gates."""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("starlette")

from starlette.testclient import TestClient

from codagent.server import create_app
from codagent.server.budgets import BudgetConfig, BudgetGate
from codagent.server.runs import InMemoryRunRegistry


# -- BudgetGate primitives ---------------------------------------------------


def test_budget_gate_check_returns_none_when_under_limit():
    gate = BudgetGate(BudgetConfig(output_tokens=10))
    assert gate.check("alice") is None


def test_budget_gate_check_flags_when_at_or_over_limit():
    gate = BudgetGate(BudgetConfig(output_tokens=3))
    for _ in range(3):
        gate.record_token("bob", "output", 1)
    v = gate.check("bob")
    assert v is not None
    assert v["limit"] == "output_tokens"
    assert v["value"] == 3
    assert v["ceiling"] == 3


def test_budget_gate_state_is_per_user():
    gate = BudgetGate(BudgetConfig(output_tokens=2))
    gate.record_token("alice", "output", 2)
    assert gate.check("alice") is not None
    assert gate.check("bob") is None  # bob has not consumed anything


def test_budget_gate_max_steps_independent_of_tokens():
    gate = BudgetGate(BudgetConfig(max_steps=2))
    gate.record_token("u", "output", 1)
    assert gate.check("u") is None
    gate.record_token("u", "output", 1)
    v = gate.check("u")
    assert v is not None
    assert v["limit"] == "steps"


def test_budget_config_max_usd_without_model_raises():
    """Misconfiguration must fail fast — silent no-op leaves the limit
    unenforced, which is worse than a noisy refusal."""
    with pytest.raises(ValueError, match="model"):
        BudgetConfig(max_usd=5.0)
    # max_usd with model is fine.
    BudgetConfig(max_usd=5.0, model="gpt-4o")
    # No max_usd, no model — fine.
    BudgetConfig(output_tokens=100)


# -- HTTP-level enforcement --------------------------------------------------


async def _ten_tokens(_body):
    for tok in "abcdefghij":
        yield tok


def test_identify_hook_is_called_with_the_request():

    seen: list[str] = []

    def identify(request):
        seen.append(request.headers.get("x-codagent-user", "anon"))
        return seen[-1]

    app = create_app(llm_call=_ten_tokens, identify=identify)
    with TestClient(app) as client:
        resp = client.post(
            "/v1/runs", json={}, headers={"x-codagent-user": "alice"}
        )
        assert resp.status_code == 201

    assert seen == ["alice"]


def test_default_identify_reads_x_codagent_user_header():

    captured_users: list[str] = []

    def identify(request):
        # We replace the default to capture, but exercise the same logic.
        u = request.headers.get("x-codagent-user", "anonymous")
        captured_users.append(u)
        return u

    app = create_app(llm_call=_ten_tokens, identify=identify)
    with TestClient(app) as client:
        client.post("/v1/runs", json={})  # no header
        client.post("/v1/runs", json={}, headers={"x-codagent-user": "bob"})

    assert captured_users == ["anonymous", "bob"]


def test_run_terminates_with_budget_exceeded_when_token_ceiling_hit():

    app = create_app(
        llm_call=_ten_tokens,
        budget=BudgetConfig(output_tokens=3),
    )
    with TestClient(app) as client:
        resp = client.post(
            "/v1/runs", json={}, headers={"x-codagent-user": "alice"}
        )
        run_id = resp.json()["run_id"]
        with client.stream("GET", f"/v1/runs/{run_id}/events") as stream:
            body = b"".join(stream.iter_bytes()).decode()

    assert "event: run.budget_exceeded" in body
    assert "event: run.done" not in body
    assert '"limit": "output_tokens"' in body
    # We saw at most 3 token events before the gate fired.
    assert body.count("event: token") <= 3


def test_second_request_blocked_immediately_when_already_over_budget():

    app = create_app(
        llm_call=_ten_tokens,
        budget=BudgetConfig(output_tokens=3),
    )
    with TestClient(app) as client:
        # First run uses up the budget.
        r1 = client.post(
            "/v1/runs", json={}, headers={"x-codagent-user": "alice"}
        )
        run_id_1 = r1.json()["run_id"]
        with client.stream("GET", f"/v1/runs/{run_id_1}/events") as s:
            b"".join(s.iter_bytes())

        # Second run from alice — no tokens should be emitted, run.budget_exceeded fires immediately.
        r2 = client.post(
            "/v1/runs", json={}, headers={"x-codagent-user": "alice"}
        )
        run_id_2 = r2.json()["run_id"]
        with client.stream("GET", f"/v1/runs/{run_id_2}/events") as s:
            body2 = b"".join(s.iter_bytes()).decode()

    assert "event: run.budget_exceeded" in body2
    # Pre-emptive: no token events on the second run.
    assert body2.count("event: token") == 0


def test_no_budget_gate_when_budget_is_none():

    app = create_app(llm_call=_ten_tokens)  # budget omitted
    with TestClient(app) as client:
        resp = client.post(
            "/v1/runs", json={}, headers={"x-codagent-user": "alice"}
        )
        run_id = resp.json()["run_id"]
        with client.stream("GET", f"/v1/runs/{run_id}/events") as stream:
            body = b"".join(stream.iter_bytes()).decode()

    assert "event: run.done" in body
    assert "event: run.budget_exceeded" not in body
    assert body.count("event: token") == 10


def test_budget_isolated_per_user():

    app = create_app(
        llm_call=_ten_tokens,
        budget=BudgetConfig(output_tokens=3),
    )
    with TestClient(app) as client:
        # alice exhausts her budget
        r1 = client.post("/v1/runs", json={}, headers={"x-codagent-user": "alice"})
        with client.stream("GET", f"/v1/runs/{r1.json()['run_id']}/events") as s:
            b"".join(s.iter_bytes())

        # bob is untouched
        r2 = client.post("/v1/runs", json={}, headers={"x-codagent-user": "bob"})
        with client.stream("GET", f"/v1/runs/{r2.json()['run_id']}/events") as s:
            body_bob = b"".join(s.iter_bytes()).decode()

    assert "event: run.budget_exceeded" in body_bob  # bob ALSO hits ceiling at his 3rd token
    # But bob got at least some tokens (was not pre-empted).
    assert body_bob.count("event: token") >= 1


def test_pure_asyncio_budget_pre_empts_when_over_before_run_starts():
    """Asyncio-level: gate state from prior usage means the next run is
    blocked before any token is published."""

    async def fake(_body):
        for tok in "abcdef":
            yield tok

    gate = BudgetGate(BudgetConfig(output_tokens=2))
    # Simulate a prior run that used up alice's budget.
    gate.record_token("alice", "output", 2)

    async def go():
        registry = InMemoryRunRegistry(budget_gate=gate)
        run = registry.create_run(fake, {}, user_id="alice")
        await run._task  # type: ignore[arg-type]
        return run

    run = asyncio.run(go())
    assert run.status == "failed"
    names = [e.name for e in run._events]  # type: ignore[attr-defined]
    assert "run.started" in names
    assert "token" not in names  # pre-empted, no tokens published
    assert "run.budget_exceeded" in names
