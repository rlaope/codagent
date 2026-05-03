"""Session storage for codagent.server.

A *session* is a client-scoped grouping of runs. Clients create a
session up front and then attach runs to it; the server can list a
session's runs so a reconnecting client can find a run it started
earlier (and replay events on it via ``Last-Event-Id``).

The default :class:`InMemorySessionStore` keeps everything in process
memory. Real backends (redis, db) implement the :class:`SessionStore`
protocol without changing the app.
"""

from __future__ import annotations

import time
import uuid
from typing import Protocol


class SessionStore(Protocol):
    """Protocol for session storage backends."""

    def create_session(self) -> str: ...

    def get_session(self, session_id: str) -> dict | None: ...

    def attach_run(self, session_id: str, run_id: str) -> None: ...

    def list_runs(self, session_id: str) -> list[str]: ...


class InMemorySessionStore:
    """Process-local session store. Default for :func:`create_app`."""

    def __init__(self) -> None:
        self._sessions: dict[str, dict] = {}

    def create_session(self) -> str:
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = {
            "session_id": session_id,
            "created_at": time.time(),
            "runs": [],
        }
        return session_id

    def get_session(self, session_id: str) -> dict | None:
        record = self._sessions.get(session_id)
        if record is None:
            return None
        return {
            "session_id": record["session_id"],
            "created_at": record["created_at"],
            "runs": list(record["runs"]),
        }

    def attach_run(self, session_id: str, run_id: str) -> None:
        record = self._sessions.get(session_id)
        if record is None:
            # Lazily create the session record if the caller skipped
            # the explicit POST /v1/sessions step.
            record = self._sessions[session_id] = {
                "session_id": session_id,
                "created_at": time.time(),
                "runs": [],
            }
        record["runs"].append(run_id)

    def list_runs(self, session_id: str) -> list[str]:
        record = self._sessions.get(session_id)
        if record is None:
            return []
        return list(record["runs"])
