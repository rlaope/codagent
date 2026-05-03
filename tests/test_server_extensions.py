"""Phase 10 — function-style hooks and custom HTTP routes/middleware."""

from __future__ import annotations

import pytest

pytest.importorskip("starlette")

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.testclient import TestClient

from codagent.server import CodagentApp


# -- Function-style RunMiddleware decorators --------------------------------


async def _two_token(_body):
    for tok in ["a", "b"]:
        yield tok


def test_before_run_decorator_registers_hook_and_can_mutate_body():
    seen_bodies: list[dict] = []

    async def capture(body):
        seen_bodies.append(dict(body))
        yield "ok"

    app = CodagentApp(capture)

    @app.before_run
    async def tag(run, body):
        body["_tagged"] = "yes"

    with TestClient(app) as client:
        resp = client.post("/v1/runs", json={"prompt": "hi"})
        run_id = resp.json()["run_id"]
        with client.stream("GET", f"/v1/runs/{run_id}/events") as stream:
            b"".join(stream.iter_bytes())

    assert seen_bodies[0]["_tagged"] == "yes"
    assert seen_bodies[0]["prompt"] == "hi"


def test_after_event_decorator_observes_every_event():
    observed: list[str] = []

    app = CodagentApp(_two_token)

    @app.after_event
    async def tap(run, event):
        observed.append(event.name)

    with TestClient(app) as client:
        resp = client.post("/v1/runs", json={})
        run_id = resp.json()["run_id"]
        with client.stream("GET", f"/v1/runs/{run_id}/events") as stream:
            b"".join(stream.iter_bytes())

    assert observed == ["run.started", "token", "token", "run.done"]


def test_after_run_decorator_fires_once_with_terminal_status():
    captured: list[str] = []

    app = CodagentApp(_two_token)

    @app.after_run
    async def cleanup(run):
        captured.append(run.status)

    with TestClient(app) as client:
        resp = client.post("/v1/runs", json={})
        run_id = resp.json()["run_id"]
        with client.stream("GET", f"/v1/runs/{run_id}/events") as stream:
            b"".join(stream.iter_bytes())

    assert captured == ["completed"]


# -- Custom routes ----------------------------------------------------------


def test_route_decorator_registers_custom_endpoint():

    app = CodagentApp(_two_token)

    @app.route("/v1/custom", methods=["GET"])
    async def handler(_request):
        return JSONResponse({"hello": "world"})

    with TestClient(app) as client:
        resp = client.get("/v1/custom")
        assert resp.status_code == 200
        assert resp.json() == {"hello": "world"}

        # Built-in routes still work alongside custom ones.
        assert client.get("/healthz").json() == {"ok": True}


def test_route_with_methods_list():

    app = CodagentApp(_two_token)

    @app.route("/v1/echo", methods=["POST"])
    async def echo(request):
        body = await request.json()
        return JSONResponse(body)

    with TestClient(app) as client:
        resp = client.post("/v1/echo", json={"a": 1})
        assert resp.json() == {"a": 1}
        # GET against POST-only route → 405.
        assert client.get("/v1/echo").status_code == 405


def test_route_after_build_raises_runtime_error():

    app = CodagentApp(_two_token)
    with TestClient(app) as client:
        client.get("/healthz")  # forces build

    with pytest.raises(RuntimeError, match="before"):

        @app.route("/v1/late")
        async def _h(_r):  # pragma: no cover - shouldn't run
            return JSONResponse({})


# -- HTTP-level Starlette middleware ----------------------------------------


def test_add_http_middleware_wires_starlette_middleware():
    """Verify HTTP middleware actually intercepts requests by adding a
    custom response header."""

    class _HeaderMW(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            response = await call_next(request)
            response.headers["x-codagent-test"] = "ok"
            return response

    app = CodagentApp(_two_token)
    app.add_http_middleware(_HeaderMW)

    with TestClient(app) as client:
        resp = client.get("/healthz")
        assert resp.headers.get("x-codagent-test") == "ok"


def test_add_http_middleware_after_build_raises():
    app = CodagentApp(_two_token)
    with TestClient(app) as client:
        client.get("/healthz")

    class _Late(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):  # pragma: no cover
            return await call_next(request)

    with pytest.raises(RuntimeError, match="before"):
        app.add_http_middleware(_Late)
