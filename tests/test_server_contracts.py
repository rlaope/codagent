"""Phase 3 — harness contracts enforced at the run boundary."""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("starlette")

from codagent.harness._abc import Contract
from codagent.server import create_app
from codagent.server.runs import InMemoryRunRegistry


class _FakeContract(Contract):
    """Test contract: configurable addendum and validate verdict."""

    def __init__(self, name: str, addendum: str, ok: bool, reason: str = "") -> None:
        self.name = name
        self._addendum = addendum
        self._ok = ok
        self._reason = reason

    def system_addendum(self) -> str:
        return self._addendum

    def validate(self, response: str) -> tuple[bool, str]:
        return (self._ok, self._reason)


def _drive(coro):
    return asyncio.run(coro)


# -- Addendum injection --------------------------------------------------------


def test_addendum_reaches_body_when_contracts_present():
    seen_bodies: list[dict] = []

    async def capture(body):
        seen_bodies.append(dict(body))
        yield "ok"

    contract = _FakeContract("c1", "ALWAYS BE CAREFUL", ok=True)

    async def go():
        registry = InMemoryRunRegistry(
            harness=__import__(
                "codagent.harness._harness", fromlist=["Harness"]
            ).Harness([contract])
        )
        run = registry.create_run(capture, {"prompt": "hi"})
        await run._task  # type: ignore[arg-type]

    _drive(go())
    assert len(seen_bodies) == 1
    assert seen_bodies[0]["_codagent_addendum"] == "ALWAYS BE CAREFUL"
    assert seen_bodies[0]["prompt"] == "hi"


def test_addendum_absent_when_no_contracts():
    seen_bodies: list[dict] = []

    async def capture(body):
        seen_bodies.append(dict(body))
        yield "ok"

    async def go():
        registry = InMemoryRunRegistry()  # no harness
        run = registry.create_run(capture, {"prompt": "hi"})
        await run._task  # type: ignore[arg-type]

    _drive(go())
    assert "_codagent_addendum" not in seen_bodies[0]


# -- Validation outcomes ------------------------------------------------------


def test_failing_contract_emits_run_contract_failed_with_names():
    async def fake(_body):
        for tok in ["plain", " answer"]:
            yield tok

    failing = _FakeContract("missing-citation", "Cite sources.", ok=False, reason="no citation")
    passing = _FakeContract("polite", "Be polite.", ok=True)

    from codagent.harness._harness import Harness

    async def go():
        registry = InMemoryRunRegistry(harness=Harness([failing, passing]))
        run = registry.create_run(fake, {})
        await run._task  # type: ignore[arg-type]
        return run

    run = _drive(go())
    assert run.status == "failed"
    terminal = run._events[-1]  # type: ignore[attr-defined]
    assert terminal.name == "run.contract_failed"
    contracts_failed = [v["contract"] for v in terminal.data["violations"]]
    assert "missing-citation" in contracts_failed
    assert "polite" not in contracts_failed
    assert terminal.data["violations"][0]["message"] == "no citation"


def test_passing_contracts_emit_run_done_not_contract_failed():
    async def fake(_body):
        for tok in ["fine", " response"]:
            yield tok

    from codagent.harness._harness import Harness

    contract = _FakeContract("polite", "Be polite.", ok=True)

    async def go():
        registry = InMemoryRunRegistry(harness=Harness([contract]))
        run = registry.create_run(fake, {})
        await run._task  # type: ignore[arg-type]
        return run

    run = _drive(go())
    assert run.status == "completed"
    names = [e.name for e in run._events]  # type: ignore[attr-defined]
    assert "run.done" in names
    assert "run.contract_failed" not in names


def test_no_contract_validation_when_run_was_cancelled():
    """A would-be-failing contract must not produce contract_failed
    if the run was cancelled before reaching natural completion."""
    contract_validate_calls: list[str] = []

    class _SpyContract(Contract):
        name = "spy"

        def system_addendum(self) -> str:
            return "spy"

        def validate(self, response: str) -> tuple[bool, str]:
            contract_validate_calls.append(response)
            return (False, "would have failed")

    async def slow(_body):
        try:
            for tok in "abcdef":
                await asyncio.sleep(0)
                yield tok
        finally:
            pass

    from codagent.harness._harness import Harness

    async def go():
        registry = InMemoryRunRegistry(harness=Harness([_SpyContract()]))
        run = registry.create_run(slow, {})

        async def cancel_after_two():
            while [e.name for e in run._events].count("token") < 2:  # type: ignore[attr-defined]
                await asyncio.sleep(0)
            run.request_cancel()

        await asyncio.gather(cancel_after_two(), run._task)  # type: ignore[arg-type]
        return run

    run = _drive(go())
    assert run.status == "cancelled"
    names = [e.name for e in run._events]  # type: ignore[attr-defined]
    assert "run.contract_failed" not in names
    assert "run.cancelled" in names
    # Validate was NOT called even though the contract would have failed.
    assert contract_validate_calls == []


# -- HTTP-level wiring --------------------------------------------------------


def test_http_create_app_accepts_contracts_kwarg_and_addendum_threads_through():
    from starlette.testclient import TestClient

    seen_bodies: list[dict] = []

    async def capture(body):
        seen_bodies.append(dict(body))
        for tok in ["a", "b"]:
            yield tok

    contract = _FakeContract("polite", "BE POLITE", ok=True)
    app = create_app(llm_call=capture, contracts=[contract])

    with TestClient(app) as client:
        resp = client.post("/v1/runs", json={"prompt": "x"})
        run_id = resp.json()["run_id"]
        with client.stream("GET", f"/v1/runs/{run_id}/events") as stream:
            body = b"".join(stream.iter_bytes()).decode()

    assert "event: run.done" in body
    assert seen_bodies[0]["_codagent_addendum"] == "BE POLITE"


def test_http_failing_contract_via_app_emits_contract_failed_event():
    from starlette.testclient import TestClient

    async def fake(_body):
        for tok in ["bad", " content"]:
            yield tok

    app = create_app(
        llm_call=fake,
        contracts=[_FakeContract("redact", "no PII", ok=False, reason="leaked PII")],
    )

    with TestClient(app) as client:
        resp = client.post("/v1/runs", json={})
        run_id = resp.json()["run_id"]
        with client.stream("GET", f"/v1/runs/{run_id}/events") as stream:
            body = b"".join(stream.iter_bytes()).decode()

    assert "event: run.contract_failed" in body
    assert "redact" in body
    assert "leaked PII" in body
    assert "event: run.done" not in body

    snap = client.get(f"/v1/runs/{run_id}").json() if False else None  # snap ineligible after exit
    # Verify status via fresh client (registry persists in app)
    with TestClient(app) as client2:
        snap = client2.get(f"/v1/runs/{run_id}").json()
    assert snap["status"] == "failed"


def test_http_no_contract_validation_when_cancelled():
    from starlette.testclient import TestClient

    async def slow(_body):
        try:
            for tok in "abcdef":
                await asyncio.sleep(0)
                yield tok
        finally:
            pass

    spy_calls: list[str] = []

    class _SpyContract(Contract):
        name = "spy"

        def system_addendum(self) -> str:
            return "spy"

        def validate(self, response: str) -> tuple[bool, str]:
            spy_calls.append(response)
            return (False, "would have failed")

    app = create_app(llm_call=slow, contracts=[_SpyContract()])

    with TestClient(app) as client:
        resp = client.post("/v1/runs", json={})
        run_id = resp.json()["run_id"]
        cancel_resp = client.post(f"/v1/runs/{run_id}/cancel")
        assert cancel_resp.status_code == 200
        with client.stream("GET", f"/v1/runs/{run_id}/events") as stream:
            body = b"".join(stream.iter_bytes()).decode()

    assert "event: run.cancelled" in body
    assert "event: run.contract_failed" not in body
    assert spy_calls == []
