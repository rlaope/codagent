"""Metrics for codagent.server.

A minimal :class:`Metrics` protocol that the registry mirrors run
lifecycle and token throughput into. Two methods:

- ``inc(name, value=1, **tags)`` — counter
- ``observe(name, value, **tags)`` — histogram-like observation

The default :class:`InMemoryMetrics` keeps everything in process for
tests and small deployments. Production wires Prometheus / OpenTelemetry
under the same protocol.

Metrics are emitted via :class:`_MetricsMiddleware`, registered
automatically when a metrics object is wired into the registry.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from codagent.server.middleware import RunMiddleware

if TYPE_CHECKING:
    from codagent.server.runs import AgentRun, RunEvent


class Metrics(Protocol):
    def inc(self, name: str, value: int = 1, **tags: str) -> None: ...

    def observe(self, name: str, value: float, **tags: str) -> None: ...


class InMemoryMetrics:
    """Process-local metrics. Counters and raw observation lists.

    Intended for tests and small single-process deployments. For
    production wire a Prometheus / OpenTelemetry adapter that
    implements the same protocol.
    """

    def __init__(self) -> None:
        self._counters: dict[tuple, int] = {}
        self._observations: dict[tuple, list[float]] = {}

    @staticmethod
    def _key(name: str, tags: dict) -> tuple:
        return (name, tuple(sorted(tags.items())))

    def inc(self, name: str, value: int = 1, **tags: str) -> None:
        key = self._key(name, tags)
        self._counters[key] = self._counters.get(key, 0) + value

    def observe(self, name: str, value: float, **tags: str) -> None:
        key = self._key(name, tags)
        self._observations.setdefault(key, []).append(value)

    def counter(self, name: str, **tags: str) -> int:
        return self._counters.get(self._key(name, tags), 0)

    def observations(self, name: str, **tags: str) -> list[float]:
        return list(self._observations.get(self._key(name, tags), []))


# Event-name → metric-name suffix mapping for terminal events.
_TERMINAL_METRIC = {
    "run.done": "completed",
    "run.cancelled": "cancelled",
    "run.failed": "failed",
    "run.contract_failed": "contract_failed",
    "run.budget_exceeded": "budget_exceeded",
}


class _MetricsMiddleware(RunMiddleware):
    """Mirror run lifecycle + token throughput into a :class:`Metrics`.

    Counters emitted::

        codagent.runs.started      — once per run
        codagent.runs.completed    — terminal: natural completion
        codagent.runs.cancelled    — terminal: cooperative cancel
        codagent.runs.failed       — terminal: upstream/middleware exception
        codagent.runs.contract_failed — terminal: harness contract violation
        codagent.runs.budget_exceeded — terminal: budget gate trip
        codagent.tokens.emitted    — once per token event
    """

    def __init__(self, metrics: Metrics) -> None:
        self._metrics = metrics

    async def before_run(self, run: "AgentRun", body: dict) -> None:
        self._metrics.inc("codagent.runs.started")

    async def after_event(self, run: "AgentRun", event: "RunEvent") -> None:
        if event.name == "token":
            self._metrics.inc("codagent.tokens.emitted")
        elif event.name in _TERMINAL_METRIC:
            self._metrics.inc(f"codagent.runs.{_TERMINAL_METRIC[event.name]}")
