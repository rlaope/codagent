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
from contextlib import asynccontextmanager

try:
    from starlette.applications import Starlette
    from starlette.middleware import Middleware
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
from codagent.server.agents import Agent
from codagent.server.budgets import BudgetConfig, BudgetGate
from codagent.server.metrics import Metrics
from codagent.server.middleware import RunMiddleware
from codagent.server.runs import (
    AgentRun,
    InMemoryRunRegistry,
    LLMCall,
    RunEvent,
    RunRegistry,
)
from codagent.server.sessions import InMemorySessionStore, SessionStore
from codagent.server.stores import BudgetStore, RunStore


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
    middleware: list[RunMiddleware] | None = None,
    run_store: RunStore | None = None,
    budget_store: BudgetStore | None = None,
    metrics: Metrics | None = None,
    max_queue_size: int = 0,
    max_events: int = 0,
    shutdown_timeout: float | None = None,
    extra_routes: list[Route] | None = None,
    http_middleware: list[Middleware] | None = None,
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
    - ``middleware`` — list of :class:`RunMiddleware` instances; their
      ``before_run`` / ``after_event`` / ``after_run`` hooks fire on
      every run.
    """

    budget_gate: BudgetGate | None = (
        BudgetGate(budget, store=budget_store) if budget is not None else None
    )
    if registry is not None:
        reg: RunRegistry = registry
    else:
        harness = Harness(list(contracts)) if contracts else None
        reg = InMemoryRunRegistry(
            harness=harness,
            budget_gate=budget_gate,
            middleware=list(middleware) if middleware else None,
            run_store=run_store,
            metrics=metrics,
            max_queue_size=max_queue_size,
            max_events=max_events,
        )
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

    @asynccontextmanager
    async def lifespan(_app):
        try:
            yield
        finally:
            # Graceful shutdown: wait for any in-flight runs so each
            # one publishes its terminal event and subscribers drain.
            shutdown = getattr(reg, "shutdown", None)
            if callable(shutdown):
                await shutdown(timeout=shutdown_timeout)

    routes: list[Route] = [
        Route("/v1/runs", create_run, methods=["POST"]),
        Route("/v1/runs/{id}", get_run, methods=["GET"]),
        Route("/v1/runs/{id}/cancel", cancel_run, methods=["POST"]),
        Route("/v1/runs/{id}/events", stream_events, methods=["GET"]),
        Route("/v1/sessions", create_session, methods=["POST"]),
        Route("/v1/sessions/{id}/runs", list_session_runs, methods=["GET"]),
        Route("/healthz", healthz, methods=["GET"]),
    ]
    if extra_routes:
        routes.extend(extra_routes)

    return Starlette(
        routes=routes,
        lifespan=lifespan,
        middleware=list(http_middleware) if http_middleware else None,
    )


class CodagentApp:
    """Class-style face for the codagent agent server.

    Wraps :func:`create_app` with decorator-style middleware
    registration and a stable ``__call__`` so the instance itself is
    directly mountable as an ASGI application::

        app = CodagentApp(MyAgent())

        @app.middleware
        class Audit(RunMiddleware): ...

        # uvicorn module:app

    Accepts either an :class:`Agent` instance or a plain ``LLMCall``
    callable. When given an :class:`Agent`, the agent's class-level
    ``contracts`` and ``middleware`` lists are picked up automatically
    and merged with anything passed at the app level.

    The underlying Starlette app is built lazily on first ASGI call so
    middleware registered via the decorator after construction is
    included.
    """

    def __init__(
        self,
        agent: "Agent | LLMCall",
        *,
        contracts: list[Contract] | None = None,
        middleware: list[RunMiddleware] | None = None,
        registry: RunRegistry | None = None,
        session_store: SessionStore | None = None,
        budget: BudgetConfig | None = None,
        identify: Callable[["Request"], str] | None = None,
        run_store: RunStore | None = None,
        budget_store: BudgetStore | None = None,
        metrics: Metrics | None = None,
        max_queue_size: int = 0,
        max_events: int = 0,
        shutdown_timeout: float | None = None,
    ) -> None:
        if isinstance(agent, Agent):
            self._llm_call: LLMCall = agent.run
            agent_contracts = list(agent.contracts)
            agent_middleware = list(agent.middleware)
        else:
            self._llm_call = agent
            agent_contracts = []
            agent_middleware = []

        self._contracts = list(contracts or []) + agent_contracts
        self._middleware = list(middleware or []) + agent_middleware
        self._registry = registry
        self._session_store = session_store
        self._budget = budget
        self._identify = identify
        self._run_store = run_store
        self._budget_store = budget_store
        self._metrics = metrics
        self._max_queue_size = max_queue_size
        self._max_events = max_events
        self._shutdown_timeout = shutdown_timeout
        self._extra_routes: list[Route] = []
        self._http_middleware: list[Middleware] = []
        self._asgi: Starlette | None = None

    def add_middleware(self, mw: RunMiddleware) -> RunMiddleware:
        """Append a middleware instance. Must be called before the app is built."""
        if self._asgi is not None:
            raise RuntimeError(
                "middleware must be registered before the first ASGI request"
            )
        self._middleware.append(mw)
        return mw

    def middleware(self, mw_or_cls):
        """Decorator: register a middleware class or instance."""
        if isinstance(mw_or_cls, type):
            self.add_middleware(mw_or_cls())
        else:
            self.add_middleware(mw_or_cls)
        return mw_or_cls

    # -- Function-style hook decorators --------------------------------------

    def before_run(self, fn):
        """Decorator: register an async function as a ``before_run`` hook.

        The function receives ``(run, body)`` and may mutate ``body`` in
        place. A raise aborts the run with ``run.failed``.
        """
        outer = fn

        class _Wrap(RunMiddleware):
            async def before_run(self, run, body):
                await outer(run, body)

        self.add_middleware(_Wrap())
        return fn

    def after_event(self, fn):
        """Decorator: register an async function as an ``after_event`` hook.

        The function receives ``(run, event)`` and is called per event.
        Errors are swallowed.
        """
        outer = fn

        class _Wrap(RunMiddleware):
            async def after_event(self, run, event):
                await outer(run, event)

        self.add_middleware(_Wrap())
        return fn

    def after_run(self, fn):
        """Decorator: register an async function as an ``after_run`` hook.

        The function receives ``(run,)`` once after the terminal event.
        Errors are swallowed.
        """
        outer = fn

        class _Wrap(RunMiddleware):
            async def after_run(self, run):
                await outer(run)

        self.add_middleware(_Wrap())
        return fn

    # -- HTTP-level extension points -----------------------------------------

    def route(self, path: str, methods: list[str] | tuple[str, ...] = ("GET",)):
        """Decorator: register a custom Starlette HTTP route on the app.

        The handler is a normal ``async def handler(request) -> Response``
        — full Starlette semantics, no codagent-specific wrapper.
        Routes registered here are mounted alongside the built-in
        ``/v1/...`` and ``/healthz`` routes.
        """
        if self._asgi is not None:
            raise RuntimeError("routes must be registered before the first ASGI request")

        def decorator(fn):
            self._extra_routes.append(Route(path, fn, methods=list(methods)))
            return fn

        return decorator

    def add_http_middleware(self, mw_cls, **kwargs) -> None:
        """Register a Starlette HTTP-level middleware class.

        Passed through to ``Starlette(middleware=[Middleware(cls, **kwargs)])``.
        For run-level hooks (``before_run``/``after_event``/``after_run``)
        use :class:`RunMiddleware` or the matching decorators instead.
        """
        if self._asgi is not None:
            raise RuntimeError("middleware must be registered before the first ASGI request")
        self._http_middleware.append(Middleware(mw_cls, **kwargs))

    def build(self) -> Starlette:
        if self._asgi is None:
            self._asgi = create_app(
                llm_call=self._llm_call,
                contracts=self._contracts or None,
                middleware=self._middleware or None,
                registry=self._registry,
                session_store=self._session_store,
                budget=self._budget,
                identify=self._identify,
                run_store=self._run_store,
                budget_store=self._budget_store,
                metrics=self._metrics,
                max_queue_size=self._max_queue_size,
                max_events=self._max_events,
                shutdown_timeout=self._shutdown_timeout,
                extra_routes=self._extra_routes or None,
                http_middleware=self._http_middleware or None,
            )
        return self._asgi

    async def __call__(self, scope, receive, send) -> None:
        await self.build()(scope, receive, send)


# Re-export the AgentRun type for convenience.
__all__ = ["create_app", "AgentRun", "CodagentApp"]
