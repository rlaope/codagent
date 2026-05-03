"""Starlette app factory for the codagent agent-server.

Endpoints:

- ``POST /v1/runs`` — start a run; returns ``{run_id, status}``
  immediately. The run executes in a background task.
- ``GET /v1/runs/{id}`` — current snapshot of a run.
- ``POST /v1/runs/{id}/cancel`` — request cooperative cancellation.
- ``GET /v1/runs/{id}/events`` — SSE stream of the run's events.
  Honours the ``Last-Event-Id`` request header for replay.
- ``GET /healthz`` — liveness probe.

The previous Phase 1 single-shot streaming POST has been replaced by
this run-as-resource model so multiple clients can subscribe to a run
and reconnect with replay.
"""

from __future__ import annotations

import asyncio
import json

try:
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import JSONResponse, Response, StreamingResponse
    from starlette.routing import Route
except ImportError as exc:  # pragma: no cover - import-time guard
    raise ImportError(
        "codagent.server requires the 'server' extra. Install with: "
        "pip install 'codagent[server]'"
    ) from exc

from typing import Callable

from codagent.harness._abc import Contract
from codagent.harness._harness import Harness
from codagent.server.budgets import BudgetConfig, BudgetGate
from codagent.server.runs import (
    AgentRun,
    InMemoryRunRegistry,
    LLMCall,
    RunEvent,
    RunRegistry,
)
from codagent.server.sessions import InMemorySessionStore, SessionStore


def _format_sse(event: RunEvent) -> str:
    payload = json.dumps(event.data) if isinstance(event.data, dict) else str(event.data)
    return f"id: {event.id}\nevent: {event.name}\ndata: {payload}\n\n"


def _default_identify(request: "Request") -> str:
    return request.headers.get("x-codagent-user", "anonymous")


def create_app(
    *,
    llm_call: LLMCall,
    registry: RunRegistry | None = None,
    contracts: list[Contract] | None = None,
    session_store: SessionStore | None = None,
    budget: BudgetConfig | None = None,
    identify: Callable[["Request"], str] | None = None,
) -> Starlette:
    """Build a Starlette app exposing the run-as-resource API.

    Optional features:

    - ``contracts`` — runtime harness validation at run boundary; failures
      emit ``run.contract_failed``.
    - ``session_store`` — server-side session/run grouping.
    - ``budget`` — per-user budget enforcement (a :class:`BudgetGate` is
      built around it). Runs that trip a limit emit
      ``run.budget_exceeded`` and terminate. State persists across runs
      for the lifetime of the app.
    - ``identify`` — Callable[[Request], str] mapping each request to a
      user id. Default: read the ``x-codagent-user`` header, fall back
      to ``"anonymous"``.
    """

    budget_gate: BudgetGate | None = BudgetGate(budget) if budget is not None else None
    if registry is not None:
        reg: RunRegistry = registry
    else:
        harness = Harness(list(contracts)) if contracts else None
        reg = InMemoryRunRegistry(harness=harness, budget_gate=budget_gate)
    sessions: SessionStore = session_store if session_store is not None else InMemorySessionStore()
    identify_fn: Callable[["Request"], str] = identify if identify is not None else _default_identify

    async def create_run(request: Request) -> Response:
        try:
            body = await request.json()
        except json.JSONDecodeError:
            return JSONResponse({"error": "body must be JSON"}, status_code=400)
        if not isinstance(body, dict):
            return JSONResponse({"error": "body must be a JSON object"}, status_code=400)
        session_id = body.pop("session_id", None) if isinstance(body.get("session_id"), str) else None
        user_id = identify_fn(request)
        run = reg.create_run(llm_call, body, user_id=user_id)
        if session_id is not None:
            sessions.attach_run(session_id, run.id)
        return JSONResponse(
            {"run_id": run.id, "status": run.status},
            status_code=201,
        )

    async def get_run(request: Request) -> Response:
        run_id = request.path_params["id"]
        run = reg.get(run_id)
        if run is None:
            return JSONResponse({"error": "run not found"}, status_code=404)
        return JSONResponse(run.snapshot())

    async def cancel_run(request: Request) -> Response:
        run_id = request.path_params["id"]
        run = reg.get(run_id)
        if run is None:
            return JSONResponse({"error": "run not found"}, status_code=404)
        run.request_cancel()
        # Wait briefly for the runner to honour the cancel so the response
        # status reflects the actual run state and any subscriber attached
        # immediately after sees the run.cancelled event in the backlog.
        task = run._task
        if task is not None:
            loop = asyncio.get_event_loop()
            deadline = loop.time() + 1.0
            while not task.done() and loop.time() < deadline:
                await asyncio.sleep(0.005)
        return JSONResponse({"run_id": run.id, "status": run.status})

    async def stream_events(request: Request) -> Response:
        run_id = request.path_params["id"]
        run = reg.get(run_id)
        if run is None:
            return JSONResponse({"error": "run not found"}, status_code=404)
        try:
            last_event_id = int(request.headers.get("last-event-id", "0"))
        except ValueError:
            last_event_id = 0

        async def gen():
            async for event in run.subscribe(last_event_id=last_event_id):
                yield _format_sse(event)

        return StreamingResponse(
            gen(),
            media_type="text/event-stream",
            headers={"cache-control": "no-cache", "x-accel-buffering": "no"},
        )

    async def create_session(_: Request) -> Response:
        session_id = sessions.create_session()
        return JSONResponse({"session_id": session_id}, status_code=201)

    async def list_session_runs(request: Request) -> Response:
        session_id = request.path_params["id"]
        if sessions.get_session(session_id) is None:
            return JSONResponse({"error": "session not found"}, status_code=404)
        return JSONResponse(
            {"session_id": session_id, "runs": sessions.list_runs(session_id)}
        )

    async def healthz(_: Request) -> JSONResponse:
        return JSONResponse({"ok": True})

    return Starlette(
        routes=[
            Route("/v1/runs", create_run, methods=["POST"]),
            Route("/v1/runs/{id}", get_run, methods=["GET"]),
            Route("/v1/runs/{id}/cancel", cancel_run, methods=["POST"]),
            Route("/v1/runs/{id}/events", stream_events, methods=["GET"]),
            Route("/v1/sessions", create_session, methods=["POST"]),
            Route("/v1/sessions/{id}/runs", list_session_runs, methods=["GET"]),
            Route("/healthz", healthz, methods=["GET"]),
        ]
    )


# Re-export the AgentRun type for convenience.
__all__ = ["create_app", "AgentRun"]
