"""Phase 6 — Agent base class + CodagentApp class face."""

from __future__ import annotations

import pytest

pytest.importorskip("starlette")

from starlette.testclient import TestClient

from codagent.harness._abc import Contract
from codagent.server import Agent, CodagentApp, RunMiddleware


class _PassContract(Contract):
    name = "pass"

    def system_addendum(self) -> str:
        return "BE GOOD"

    def validate(self, response: str) -> tuple[bool, str]:
        return (True, "")


def test_agent_subclass_runs_via_codagentapp():
    class MyAgent(Agent):
        async def run(self, body):
            for tok in body.get("prompt", "x").split():
                yield tok

    app = CodagentApp(MyAgent())
    with TestClient(app) as client:
        resp = client.post("/v1/runs", json={"prompt": "alpha beta"})
        assert resp.status_code == 201
        run_id = resp.json()["run_id"]
        with client.stream("GET", f"/v1/runs/{run_id}/events") as stream:
            body = b"".join(stream.iter_bytes()).decode()

    assert body.count("event: token") == 2
    assert "event: run.done" in body


def test_agent_class_level_contracts_are_picked_up():
    seen_bodies: list[dict] = []

    class _CapturingAgent(Agent):
        contracts = [_PassContract()]

        async def run(self, body):
            seen_bodies.append(dict(body))
            yield "ok"

    app = CodagentApp(_CapturingAgent())
    with TestClient(app) as client:
        resp = client.post("/v1/runs", json={})
        run_id = resp.json()["run_id"]
        with client.stream("GET", f"/v1/runs/{run_id}/events") as stream:
            b"".join(stream.iter_bytes())

    # The contract's system_addendum was threaded into the LLM body.
    assert seen_bodies[0]["_codagent_addendum"] == "BE GOOD"


def test_agent_class_level_middleware_are_picked_up():
    observed: list[str] = []

    class _Tap(RunMiddleware):
        async def after_event(self, run, event):
            observed.append(event.name)

    class _MyAgent(Agent):
        middleware = [_Tap()]

        async def run(self, body):
            yield "x"

    app = CodagentApp(_MyAgent())
    with TestClient(app) as client:
        resp = client.post("/v1/runs", json={})
        run_id = resp.json()["run_id"]
        with client.stream("GET", f"/v1/runs/{run_id}/events") as stream:
            b"".join(stream.iter_bytes())

    assert observed == ["run.started", "token", "run.done"]


def test_codagentapp_accepts_plain_function():
    async def fake(_body):
        for tok in ["a", "b"]:
            yield tok

    app = CodagentApp(fake)
    with TestClient(app) as client:
        resp = client.post("/v1/runs", json={})
        run_id = resp.json()["run_id"]
        with client.stream("GET", f"/v1/runs/{run_id}/events") as stream:
            body = b"".join(stream.iter_bytes()).decode()

    assert body.count("event: token") == 2


def test_codagentapp_middleware_decorator_registers_class():
    async def fake(_body):
        yield "ok"

    app = CodagentApp(fake)
    observed: list[str] = []

    @app.middleware
    class _Audit(RunMiddleware):
        async def after_event(self, run, event):
            observed.append(event.name)

    with TestClient(app) as client:
        resp = client.post("/v1/runs", json={})
        run_id = resp.json()["run_id"]
        with client.stream("GET", f"/v1/runs/{run_id}/events") as stream:
            b"".join(stream.iter_bytes())

    assert observed == ["run.started", "token", "run.done"]


def test_codagentapp_add_middleware_after_build_raises():
    async def fake(_body):
        yield "ok"

    app = CodagentApp(fake)
    # Force build
    with TestClient(app) as client:
        client.get("/healthz")

    class _Late(RunMiddleware):
        pass

    with pytest.raises(RuntimeError, match="before"):
        app.add_middleware(_Late())


def test_app_level_middleware_merges_with_agent_middleware():
    order: list[str] = []

    class _AgentMw(RunMiddleware):
        async def before_run(self, run, body):
            order.append("agent")

    class _AppMw(RunMiddleware):
        async def before_run(self, run, body):
            order.append("app")

    class _A(Agent):
        middleware = [_AgentMw()]

        async def run(self, body):
            yield "x"

    app = CodagentApp(_A(), middleware=[_AppMw()])
    with TestClient(app) as client:
        resp = client.post("/v1/runs", json={})
        run_id = resp.json()["run_id"]
        with client.stream("GET", f"/v1/runs/{run_id}/events") as stream:
            b"".join(stream.iter_bytes())

    # Both fire; app-level was registered first per CodagentApp.__init__.
    assert order == ["app", "agent"]


def test_agent_default_run_raises():
    """A user that forgets to override `run` gets a clear error."""
    import asyncio

    bare = Agent()

    async def go():
        with pytest.raises(NotImplementedError):
            async for _ in bare.run({}):
                pass

    asyncio.run(go())
