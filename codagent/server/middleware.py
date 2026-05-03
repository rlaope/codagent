"""Run lifecycle middleware for codagent.server.

A middleware observes (and may mutate) a run at three points:

- ``before_run`` — once, before the LLM call starts. May modify ``body``
  in place. Raising aborts the run with ``run.failed``.
- ``after_event`` — once per published event (``run.started``, ``token``,
  terminal events). Errors are swallowed so a buggy middleware can't
  break the run; production callers should add their own logging.
- ``after_run`` — once, after the terminal event is published. Errors
  are swallowed.

Subclass :class:`RunMiddleware` and override only the hooks you need;
the base methods are no-ops.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from codagent.server.runs import AgentRun, RunEvent


class RunMiddleware:
    """Base class for run-lifecycle middleware.

    All hooks are async no-ops by default. Subclasses override only the
    hooks they need. Three rules to know:

    1. ``before_run`` runs *before* the run goes from ``queued`` to
       ``running``; the ``body`` dict is mutable and changes are visible
       to the LLM call.
    2. ``after_event`` runs after the event is added to history and put
       on every subscriber's queue, so subscribers may already be
       processing it. Don't expect ordering guarantees against
       subscribers.
    3. ``after_run`` runs after the terminal event has been published
       and the run is marked done; cleanup hook for resources tied to
       the run's lifetime.
    """

    async def before_run(self, run: "AgentRun", body: dict) -> None:
        return None

    async def after_event(self, run: "AgentRun", event: "RunEvent") -> None:
        return None

    async def after_run(self, run: "AgentRun") -> None:
        return None
