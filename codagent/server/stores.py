"""Persistence backend protocols for codagent.server.

The server's stateful pieces — run history, budget state — are kept
behind narrow protocols so the in-memory defaults can be swapped for
Redis, Postgres, or any other backend without touching the app layer.

Two backends are abstracted here:

- :class:`BudgetStore` — per-user budget counters. Synchronous because
  the in-process default is the hot path; async backends should run
  their own client in a thread pool or wrap with a sync-compatible
  helper.
- :class:`RunStore` — run snapshots plus event history. Async because
  real backends are network-bound.

Two in-memory defaults — :class:`InMemoryBudgetStore` and
:class:`InMemoryRunStore` — are provided for tests and
single-process deployments. A small :class:`_RunStoreMirror`
middleware mirrors run events into a :class:`RunStore` automatically
when a run store is wired into the registry.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from codagent.server.middleware import RunMiddleware

if TYPE_CHECKING:
    from codagent.server.runs import AgentRun, RunEvent


class BudgetStore(Protocol):
    """Per-user budget state storage.

    Stored shape::

        {
          "input_tokens": int,
          "output_tokens": int,
          "usd": float,
          "steps": int,
        }

    The store contract: :meth:`get` returns the current snapshot
    (zero-initialised on first read); :meth:`set` overwrites the whole
    snapshot. Distributed implementations are responsible for
    atomicity if they want strong cross-worker consistency.
    """

    def get(self, user_id: str) -> dict: ...

    def set(self, user_id: str, state: dict) -> None: ...


class InMemoryBudgetStore:
    """Process-local budget store. Default for :class:`BudgetGate`."""

    _ZERO = {"input_tokens": 0, "output_tokens": 0, "usd": 0.0, "steps": 0}

    def __init__(self) -> None:
        self._state: dict[str, dict] = {}

    def get(self, user_id: str) -> dict:
        s = self._state.get(user_id)
        return dict(s) if s is not None else dict(self._ZERO)

    def set(self, user_id: str, state: dict) -> None:
        self._state[user_id] = dict(state)


class RunStore(Protocol):
    """Run snapshot + event history persistence.

    A run's in-memory :class:`AgentRun` keeps its own event list for
    fast same-process replay; :class:`RunStore` is the cross-process /
    post-restart durability layer. The registry mirrors writes to it
    via :class:`_RunStoreMirror` (installed automatically when a store
    is provided).
    """

    async def save_snapshot(self, snapshot: dict) -> None: ...

    async def load_snapshot(self, run_id: str) -> dict | None: ...

    async def append_event(self, run_id: str, event: "RunEvent") -> None: ...

    async def get_events(
        self, run_id: str, after_id: int = 0
    ) -> "list[RunEvent]": ...


class InMemoryRunStore:
    """Process-local run store. Default for tests and single-process apps."""

    def __init__(self) -> None:
        self._snapshots: dict[str, dict] = {}
        self._events: dict[str, list] = {}

    async def save_snapshot(self, snapshot: dict) -> None:
        self._snapshots[snapshot["run_id"]] = dict(snapshot)

    async def load_snapshot(self, run_id: str) -> dict | None:
        snap = self._snapshots.get(run_id)
        return dict(snap) if snap is not None else None

    async def append_event(self, run_id: str, event: "RunEvent") -> None:
        self._events.setdefault(run_id, []).append(event)

    async def get_events(
        self, run_id: str, after_id: int = 0
    ) -> "list[RunEvent]":
        return [e for e in self._events.get(run_id, []) if e.id > after_id]


class _RunStoreMirror(RunMiddleware):
    """Middleware that mirrors a run's events into a :class:`RunStore`.

    Installed automatically by :class:`InMemoryRunRegistry` when a
    ``run_store`` is provided. End users typically don't construct
    this directly.
    """

    def __init__(self, store: RunStore) -> None:
        self._store = store

    async def before_run(self, run: "AgentRun", body: dict) -> None:
        await self._store.save_snapshot(run.snapshot())

    async def after_event(self, run: "AgentRun", event: "RunEvent") -> None:
        await self._store.append_event(run.id, event)

    async def after_run(self, run: "AgentRun") -> None:
        await self._store.save_snapshot(run.snapshot())
