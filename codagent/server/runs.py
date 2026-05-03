"""Run lifecycle and registry for codagent.server.

A run is an addressable, multi-subscriber, replayable stream of events
produced by an :data:`LLMCall` async generator. The runtime decouples a
run from any single HTTP connection so that:

- A client can ``POST /v1/runs`` without blocking on the LLM stream.
- Multiple clients can ``GET /v1/runs/{id}/events`` concurrently and see
  the same event sequence.
- A reconnecting client can pass ``Last-Event-Id`` to skip already-seen
  events and pick up the rest.
- ``POST /v1/runs/{id}/cancel`` stops the upstream generator
  cooperatively (its ``finally`` block runs).
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, AsyncGenerator, AsyncIterator, Callable, Protocol

if TYPE_CHECKING:
    from codagent.harness._harness import Harness
    from codagent.server.budgets import BudgetGate


LLMCall = Callable[[dict], AsyncIterator[str]]

_SENTINEL: object = object()


@dataclass
class RunEvent:
    """A single event emitted from a run.

    Attributes
    ----------
    id:
        Monotonic, per-run identifier. Used as the SSE ``id:`` field and
        as the value clients echo back in ``Last-Event-Id`` for replay.
    name:
        Event type, e.g. ``run.started``, ``token``, ``run.done``,
        ``run.cancelled``, ``run.failed``.
    data:
        Arbitrary JSON-serialisable payload.
    """

    id: int
    name: str
    data: dict


@dataclass
class AgentRun:
    """One in-flight agent run plus its event history and subscribers.

    The run is started in the background by :class:`InMemoryRunRegistry`;
    callers interact with it through :meth:`subscribe`, :meth:`snapshot`
    and :meth:`request_cancel`.
    """

    id: str
    status: str = "queued"
    created_at: float = field(default_factory=time.time)
    finished_at: float | None = None

    _events: list[RunEvent] = field(default_factory=list)
    _next_id: int = 0
    _subscribers: list[asyncio.Queue] = field(default_factory=list)
    _cancel_requested: bool = False
    _lock: asyncio.Lock | None = field(default=None, repr=False)
    _done: asyncio.Event | None = field(default=None, repr=False)
    _task: asyncio.Task | None = field(default=None, repr=False)

    # asyncio primitives bind to the running loop; create them lazily.
    def _ensure_async_state(self) -> None:
        if self._lock is None:
            self._lock = asyncio.Lock()
        if self._done is None:
            self._done = asyncio.Event()

    async def publish(self, name: str, data: dict) -> RunEvent:
        """Append an event to history and broadcast it to all subscribers."""
        self._ensure_async_state()
        assert self._lock is not None
        async with self._lock:
            self._next_id += 1
            event = RunEvent(id=self._next_id, name=name, data=dict(data))
            self._events.append(event)
            for queue in list(self._subscribers):
                queue.put_nowait(event)
        return event

    async def subscribe(
        self, last_event_id: int = 0
    ) -> AsyncGenerator[RunEvent, None]:
        """Yield events with ``id > last_event_id`` until the run terminates.

        Newly-attaching subscribers first receive the backlog (events
        already in history past ``last_event_id``), then live events.
        Returns when the run is done and there are no more events to
        deliver.
        """
        self._ensure_async_state()
        assert self._lock is not None and self._done is not None

        queue: asyncio.Queue = asyncio.Queue()
        async with self._lock:
            for event in self._events:
                if event.id > last_event_id:
                    queue.put_nowait(event)
            if self._done.is_set():
                queue.put_nowait(_SENTINEL)
            else:
                self._subscribers.append(queue)
        try:
            while True:
                event = await queue.get()
                if event is _SENTINEL:
                    return
                yield event
        finally:
            async with self._lock:
                if queue in self._subscribers:
                    self._subscribers.remove(queue)

    async def mark_done(self) -> None:
        """Signal end-of-stream to all subscribers."""
        self._ensure_async_state()
        assert self._lock is not None and self._done is not None
        async with self._lock:
            self._done.set()
            for queue in list(self._subscribers):
                queue.put_nowait(_SENTINEL)
            self._subscribers.clear()

    def request_cancel(self) -> None:
        """Request cooperative cancellation. The runner exits at the next yield."""
        self._cancel_requested = True

    @property
    def cancel_requested(self) -> bool:
        return self._cancel_requested

    def snapshot(self) -> dict:
        return {
            "run_id": self.id,
            "status": self.status,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
        }


async def run_task(
    run: AgentRun,
    llm_call: LLMCall,
    body: dict,
    harness: "Harness | None" = None,
    budget_gate: "BudgetGate | None" = None,
    user_id: str = "",
) -> None:
    """Background task body: drive an :data:`LLMCall` and publish events.

    Terminal events (exactly one is emitted):
        * ``run.done`` — natural completion, contracts pass.
        * ``run.contract_failed`` — natural completion but contracts fail.
        * ``run.budget_exceeded`` — user budget tripped (pre-emptively or
          mid-stream).
        * ``run.cancelled`` — explicit or hard cancel.
        * ``run.failed`` — upstream exception.

    Cooperative cancellation: callers set ``run.cancel_requested`` and
    the runner exits between tokens so the upstream async generator's
    ``finally`` block runs naturally.
    """
    failed: str | None = None
    accumulated: list[str] = []
    budget_violation: dict | None = None
    try:
        run.status = "running"
        await run.publish("run.started", {"run_id": run.id})

        # Pre-emptive budget check: a user already over the ceiling is
        # rejected without even starting the upstream call.
        if budget_gate is not None:
            violation = budget_gate.check(user_id)
            if violation is not None:
                budget_violation = violation
                run._cancel_requested = True

        if not run.cancel_requested:
            agen = llm_call(body)
            try:
                async for token in agen:
                    if run.cancel_requested:
                        break
                    accumulated.append(token)
                    if budget_gate is not None:
                        budget_gate.record_token(user_id, "output", 1)
                        violation = budget_gate.check(user_id)
                        if violation is not None:
                            budget_violation = violation
                            run._cancel_requested = True
                            break
                    await run.publish("token", {"text": token})
            finally:
                aclose = getattr(agen, "aclose", None)
                if aclose is not None:
                    try:
                        await aclose()
                    except BaseException:
                        pass

    except asyncio.CancelledError:
        # External hard-cancel: treat as a cooperative cancel for cleanup.
        run._cancel_requested = True
        current = asyncio.current_task()
        if current is not None:
            uncancel = getattr(current, "uncancel", None)
            if uncancel is not None:
                uncancel()
    except Exception as exc:
        failed = str(exc) or exc.__class__.__name__

    if failed is not None:
        run.status = "failed"
        await run.publish("run.failed", {"run_id": run.id, "error": failed})
    elif budget_violation is not None:
        run.status = "failed"
        await run.publish(
            "run.budget_exceeded",
            {"run_id": run.id, **budget_violation},
        )
    elif run.cancel_requested:
        run.status = "cancelled"
        await run.publish("run.cancelled", {"run_id": run.id})
    else:
        violations = _validate_with_harness(harness, "".join(accumulated))
        if violations:
            run.status = "failed"
            await run.publish(
                "run.contract_failed",
                {"run_id": run.id, "violations": violations},
            )
        else:
            run.status = "completed"
            await run.publish("run.done", {"run_id": run.id})

    run.finished_at = time.time()
    await run.mark_done()


def _validate_with_harness(harness, response: str) -> list[dict]:
    """Run ``harness.validate`` on the response. Return list of violations."""
    if harness is None or not harness.contracts:
        return []
    results = harness.validate(response)
    return [
        {"contract": name, "message": payload.get("reason") or ""}
        for name, payload in results.items()
        if name != "all_ok" and isinstance(payload, dict) and not payload.get("ok")
    ]


class RunRegistry(Protocol):
    """Protocol for run storage backends.

    The default :class:`InMemoryRunRegistry` keeps everything in process
    memory; alternative backends (redis, db) can implement this protocol
    without modifying the app.
    """

    def create_run(
        self, llm_call: LLMCall, body: dict, *, user_id: str = ""
    ) -> AgentRun: ...

    def get(self, run_id: str) -> AgentRun | None: ...


class InMemoryRunRegistry:
    """Process-local run registry.

    Accepts an optional :class:`Harness` whose contracts are validated
    against the run's accumulated output on natural completion (the
    addendum is exposed to ``llm_call`` via ``body["_codagent_addendum"]``)
    and an optional :class:`BudgetGate` for per-user limit enforcement.
    """

    def __init__(
        self,
        harness: "Harness | None" = None,
        budget_gate: "BudgetGate | None" = None,
    ) -> None:
        self._runs: dict[str, AgentRun] = {}
        self._harness = harness
        self._budget_gate = budget_gate

    def create_run(
        self, llm_call: LLMCall, body: dict, *, user_id: str = ""
    ) -> AgentRun:
        if self._harness is not None and self._harness.contracts:
            body = dict(body)
            body["_codagent_addendum"] = self._harness.system_addendum()
        run = AgentRun(id=str(uuid.uuid4()))
        run._task = asyncio.create_task(
            run_task(
                run,
                llm_call,
                body,
                harness=self._harness,
                budget_gate=self._budget_gate,
                user_id=user_id,
            )
        )
        self._runs[run.id] = run
        return run

    def get(self, run_id: str) -> AgentRun | None:
        return self._runs.get(run_id)
