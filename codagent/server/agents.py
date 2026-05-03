"""Agent base class for codagent.server.

This is *optional*. The function-style ``llm_call`` API still works
end-to-end. The ``Agent`` base exists for users who want to bundle
behaviour (the streaming run logic), contracts, and middleware in one
place — typical when an agent owns long-lived state (db handles,
tool registries, memory) that is awkward to express as a closure.

Usage::

    class MyAgent(Agent):
        contracts = [CitationRequired()]

        async def run(self, body):
            for tok in body["prompt"].split():
                yield tok

    app = CodagentApp(MyAgent())

The :class:`CodagentApp` reads ``contracts`` and ``middleware`` off the
agent instance and merges them with anything passed at the app level.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, AsyncIterator

if TYPE_CHECKING:
    from codagent.harness._abc import Contract
    from codagent.server.middleware import RunMiddleware


class Agent:
    """Optional base class for codagent agents.

    Subclass and implement :meth:`run` as an async generator yielding
    string tokens. Class-level attributes ``contracts`` and
    ``middleware`` are picked up by :class:`CodagentApp` automatically.
    """

    contracts: "list[Contract]" = []
    middleware: "list[RunMiddleware]" = []

    async def run(self, body: dict) -> AsyncIterator[str]:
        raise NotImplementedError(
            "Agent subclasses must implement `async def run(self, body)`"
        )
        # Make the type-checker treat this as an async generator.
        if False:  # pragma: no cover
            yield ""
