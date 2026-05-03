"""Starlette app factory for the codagent agent-server.

Exposes a single endpoint, ``POST /v1/runs``, that streams the output of an
async-generator LLM callable as Server-Sent Events. The endpoint polls
``request.is_disconnected()`` between yielded tokens; if the client has
disconnected, the loop exits and the LLM async generator is closed,
which propagates ``CancelledError`` into the upstream call.
"""

from __future__ import annotations

import json
import uuid
from typing import AsyncIterator, Awaitable, Callable

try:
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import JSONResponse, StreamingResponse
    from starlette.routing import Route
except ImportError as exc:  # pragma: no cover - import-time guard
    raise ImportError(
        "codagent.server requires the 'server' extra. Install with: "
        "pip install 'codagent[server]'"
    ) from exc


# An async-generator callable: takes the parsed JSON body, yields token
# strings. Must respect asyncio.CancelledError to participate in cancel
# propagation when the client disconnects.
LLMCall = Callable[[dict], AsyncIterator[str]]


def _sse(event: str, data: dict | str) -> str:
    payload = data if isinstance(data, str) else json.dumps(data)
    return f"event: {event}\ndata: {payload}\n\n"


async def _run_stream(
    llm_call: LLMCall,
    body: dict,
    is_disconnected: Callable[[], Awaitable[bool]],
) -> AsyncIterator[str]:
    """Core SSE event generator. Pulled out for direct testability.

    Yields raw SSE-formatted strings. Polls ``is_disconnected`` between
    tokens; on disconnect, emits ``run.cancelled`` and returns, which
    closes the underlying ``llm_call`` async generator.
    """
    run_id = str(uuid.uuid4())
    yield _sse("run.started", {"run_id": run_id})
    agen = llm_call(body)
    try:
        async for token in agen:
            if await is_disconnected():
                yield _sse("run.cancelled", {"run_id": run_id})
                return
            yield _sse("token", {"text": token})
        yield _sse("run.done", {"run_id": run_id})
    finally:
        aclose = getattr(agen, "aclose", None)
        if aclose is not None:
            await aclose()


def create_app(*, llm_call: LLMCall) -> Starlette:
    """Build a Starlette app that serves the given LLM callable.

    The app exposes:

    - ``POST /v1/runs`` — body JSON is passed to ``llm_call``; tokens
      stream back as SSE ``token`` events. Emits ``run.started`` first
      and ``run.done`` (or ``run.cancelled``) last.
    - ``GET /healthz`` — returns ``{"ok": true}``.
    """

    async def create_run(request: Request) -> StreamingResponse:
        try:
            body = await request.json()
        except json.JSONDecodeError:
            return JSONResponse({"error": "body must be JSON"}, status_code=400)

        return StreamingResponse(
            _run_stream(llm_call, body, request.is_disconnected),
            media_type="text/event-stream",
            headers={"cache-control": "no-cache", "x-accel-buffering": "no"},
        )

    async def healthz(_: Request) -> JSONResponse:
        return JSONResponse({"ok": True})

    return Starlette(
        routes=[
            Route("/v1/runs", create_run, methods=["POST"]),
            Route("/healthz", healthz, methods=["GET"]),
        ]
    )
