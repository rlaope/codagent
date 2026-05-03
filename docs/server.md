# codagent.server — agent-native HTTP server engine

A server runtime purpose-built for long-running LLM agent runs, where the
plain REST/FastAPI pattern falls short.

## Why this exists

| Concern | Plain REST app | `codagent.server` |
|---|---|---|
| Response shape | one JSON return | streaming SSE tokens |
| Client disconnect | upstream LLM call keeps running, tokens keep billing | cancel propagates, upstream call stops |
| Multi-step run state | none | run id, status, reconnectable stream |
| Per-user budgets | enforced ad hoc in app code | enforced at the server boundary |
| Harness contracts | wrap client manually | applied at the run boundary |

The server stays up; only the one user's run gets cancelled when that
user disconnects.

## Roadmap

### Phase 1 — DONE: streaming + disconnect-cancel

Already shipped:

- `POST /v1/runs` — SSE stream of token events
- `GET /healthz`
- Disconnect detection via `request.is_disconnected()` polled between
  tokens; closes the upstream `LLMCall` async generator on disconnect
  (emits `run.cancelled`)
- `codagent serve module:attr` CLI
- 5 tests in `tests/test_server.py`

### Phase 2 — run lifecycle (next)

Promote a "run" from a single fire-and-forget endpoint to a proper
addressable resource.

- `POST /v1/runs` — create run; return `{run_id, status: "queued"}`
  immediately; start the run in a background task
- `GET /v1/runs/{id}/events` — SSE stream of run events; safe to open
  more than once; supports `Last-Event-Id` for replay-on-reconnect
- `POST /v1/runs/{id}/cancel` — explicit cancel from any client
- `GET /v1/runs/{id}` — status snapshot

In-memory `RunRegistry` first. Pluggable backend interface so Phase 4
can swap in redis/db.

### Phase 3 — harness integration

Apply the existing `codagent.harness` contracts at the run boundary
instead of (or in addition to) the client level:

```python
from codagent.harness import AssumptionSurface, VerificationLoop
from codagent.server import create_app

app = create_app(
    llm_call=my_run,
    contracts=[AssumptionSurface(min_items=2), VerificationLoop()],
)
```

The server injects the harness addendum into the request and validates
the final assistant message; failure emits `run.contract_failed` with
the violations.

### Phase 4 — sessions & resume

- `POST /v1/sessions` → `{session_id}`
- Runs created under a `session_id` are persisted; reconnecting clients
  can resume the latest run's stream from a given event id
- `SessionStore` protocol — default in-memory; optional redis backend
  exposed under a `codagent[server-redis]` extra

### Phase 5 — per-user budgets

Reuse `CostTracker` and `StepBudget` from `codagent.observability`.
A `BudgetGate` middleware attaches to each run; over-budget runs emit
`run.budget_exceeded` and terminate. Budget keys come from a pluggable
`identify(request) -> user_id` hook; default reads `x-codagent-user`.

## Out of scope (for now)

- Authentication / authorization (BYO middleware)
- Multi-tenant isolation beyond budget keys
- Distributed run scheduling — single-process assumption through Phase 5

## Layout

```
codagent/server/
  __init__.py      exports create_app
  app.py           Starlette factory, _run_stream core   [Phase 1 done]
  runs.py          RunRegistry, AgentRun                 [Phase 2]
  sessions.py     SessionStore protocol                  [Phase 4]
  budgets.py       BudgetGate                            [Phase 5]
```

CLI entry lives in `codagent/cli.py` (`serve` subcommand, Phase 1 done).

## Test discipline

Every phase adds a test file under `tests/`. Each differentiator gets a
unit-level test that does not require a real network: cancel
propagation, run resumption, contract enforcement, and budget cutoff
must each be reproducible from `pytest -q`.
