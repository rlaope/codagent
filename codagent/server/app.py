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

from codagent.server.runs import (
    AgentRun,
    InMemoryRunRegistry,
    LLMCall,
    RunEvent,
    RunRegistry,
)


def _format_sse(event: RunEvent) -> str:
    payload = json.dumps(event.data) if isinstance(event.data, dict) else str(event.data)
    return f"id: {event.id}\nevent: {event.name}\ndata: {payload}\n\n"


def create_app(
    *,
    llm_call: LLMCall,
    registry: RunRegistry | None = None,
) -> Starlette:
    """Build a Starlette app exposing the run-as-resource API."""

    reg: RunRegistry = registry if registry is not None else InMemoryRunRegistry()

    async def create_run(request: Request) -> Response:
        try:
            body = await request.json()
        except json.JSONDecodeError:
            return JSONResponse({"error": "body must be JSON"}, status_code=400)
        if not isinstance(body, dict):
            return JSONResponse({"error": "body must be a JSON object"}, status_code=400)
        run = reg.create_run(llm_call, body)
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

    async def healthz(_: Request) -> JSONResponse:
        return JSONResponse({"ok": True})

    return Starlette(
        routes=[
            Route("/v1/runs", create_run, methods=["POST"]),
            Route("/v1/runs/{id}", get_run, methods=["GET"]),
            Route("/v1/runs/{id}/cancel", cancel_run, methods=["POST"]),
            Route("/v1/runs/{id}/events", stream_events, methods=["GET"]),
            Route("/healthz", healthz, methods=["GET"]),
        ]
    )


# Re-export the AgentRun type for convenience.
__all__ = ["create_app", "AgentRun"]
