"""codagent.server — agent-native HTTP server engine.

Goes beyond the FastAPI/RESTful pattern with primitives that matter for
long-running LLM agent runs:

- Streaming responses over Server-Sent Events
- Client-disconnect detection with cancel propagation into the LLM call
  (so a closed browser tab stops burning tokens immediately)

Install with the optional ``server`` extra::

    pip install 'codagent[server]'

Quick start::

    # myagent.py
    async def run(body):
        # Async generator yielding token strings.
        # Must respect asyncio.CancelledError for cancel propagation to work.
        for token in body["prompt"].split():
            yield token

Serve with::

    codagent serve myagent:run --port 8000

Then::

    curl -N -X POST http://localhost:8000/v1/runs \\
         -H 'content-type: application/json' \\
         -d '{"prompt": "hello world"}'
"""

from codagent.server.agents import Agent
from codagent.server.app import CodagentApp, create_app
from codagent.server.middleware import RunMiddleware

__all__ = ["create_app", "CodagentApp", "Agent", "RunMiddleware"]
