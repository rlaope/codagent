# CHANGELOG

Version history for codagent.

## v0.5.0 (current)

**Production safety release — three new guardrails for runaway agents.**

Each addition fills a gap LangGraph leaves to the developer and is
independently small enough to audit (~30–80 lines + tests). All three
were prioritized after surveying production agent failure modes
documented in 2025–2026 LangGraph/LangChain post-mortems.

### Added

- `BudgetCap` (`codagent.observability.BudgetCap`): hard USD ceiling
  on top of a `CostTracker`. Raises `BudgetExceeded` once cumulative
  spend crosses the cap. Two modes: route LLM calls through
  `cap.record_call(...)` for auto-check, or call `cap.check()` at
  graph step boundaries. Multiple caps can observe one tracker (e.g.
  per-run + per-day). Closes the "$200 silent retry loop" failure
  mode that LangGraph itself leaves to the user.

- `with_loop_guard` (`codagent.nodes.with_loop_guard`): wraps a tool
  or node and tracks fingerprints of recent invocations. After
  `max_repeats` identical fingerprints inside a rolling `window`,
  raises `LoopDetected`. Catches the classic agent thrashing failure
  mode (same tool, same args, dozens of calls). Default fingerprint
  JSON-serializes args/kwargs; pass `key_fn=` to override. Each
  wrapped callable owns its own counter, so wrapping twice gives
  independent state.

- `FaithfulnessContract` (`codagent.harness.FaithfulnessContract`):
  RAG-grounding contract — LLM-as-judge over `(retrieved_context,
  response)` to detect claims not grounded in context. Catches the
  failure mode where `CitationRequired` passes (markers present) but
  the cited fact was hallucinated. RAGAS-style without the dependency.
  Stateful: call `contract.set_context(docs)` after retrieval; or pass
  `context_provider=` for lazy lookup. Skips gracefully when no judge
  or no context is configured.

### Why these three (and not others)

Surveyed gaps:

| Pattern | Already covered? | Decision |
|---|---|---|
| Cost ceiling / kill switch | LangGraph leaves to user | **add `BudgetCap`** |
| Tool loop / thrashing | LangChain middleware partial | **add `with_loop_guard`** |
| RAG grounding (faithfulness) | `CitationRequired` (regex) only | **add `FaithfulnessContract`** |
| Prompt caching helper | LiteLLM, Instructor, Pydantic AI cover this | skip (saturated) |
| Chunking utilities | LangChain text_splitters / unstructured.io | skip (scope creep) |
| Long-term memory | Mem0 / Letta / AgentCore | skip (infra domain) |
| Web scraping | Firecrawl / Trafilatura / Jina Reader | skip (different domain) |
| Checkpointing | LangGraph native | skip (already there) |

### Tests

- 5 new `BudgetCap` tests in `tests/test_observability.py`
- 8 new `with_loop_guard` tests in `tests/test_nodes.py`
- 11 new `FaithfulnessContract` tests in `tests/test_contracts.py`

Total: 110 tests passing (was 86 in v0.4.1).

## v0.4.1

**Patch — discovered while dogfooding via codagent-rag-demo.**

### Fixed

- `VerificationLoop`: evidence regex now also matches `pytest passed`
  (the previous `\btest(?:s)?\s+passed\b` pattern was blocked by the
  word boundary inside `pytest`). Pattern is now
  `\b(?:py)?test(?:s)?\s+passed\b`.

### Documented

- README install section: noted Python 3.14 incompatibility with
  setuptools editable installs (`__editable__.*.pth` files are skipped
  on 3.14 because their names start with `_`). Recommend a non-editable
  install or Python 3.13 / 3.12 for editable workflows.

## v0.4.0

**Alpha release**

### Added

- `Harness` composer: mix contracts and HarnessSource instances
- `AssumptionSurface` contract: force agents to surface assumptions
- `VerificationLoop` contract: force agents to back claims with evidence
- `ToolCallSurface` contract: force agents to declare tool intent
- `RefusalPattern` contract: force explicit refusals for sensitive keywords
- `CitationRequired` contract: force factual claims to carry `[source: ...]`
- `MetaAgentContract`: delegate validation to an LLM judge
- Node wrappers: `with_retry`, `with_timeout`, `with_cache`, `parse_structured`
- Tool decorators: `validated_tool`, `circuit_breaker`, `rate_limit`
- Observability: `CostTracker`, `StepBudget`, `StepCounter`, `StateTracer`
- Framework integrations:
  - `wrap_openai` for OpenAI Python SDK
  - `wrap_anthropic` for Anthropic Python SDK
  - `HarnessRunnable` and `make_harness_callback_handler` for LangChain
  - `assumption_surface_node` and `verification_gate` for LangGraph
  - `pydantic_ai_prompt` for Pydantic AI
  - `HarnessLlamaIndexCallback` for LlamaIndex
- Comprehensive documentation with module guides, framework guides, and production guides

### Known issues

- `with_timeout` uses thread pools; timed-out nodes continue in background and may leak resources
- `with_cache` is not thread-safe in v0.4.0; wrap with a lock for concurrent graph execution
- `MetaAgentContract` makes synchronous LLM calls; async judge support planned for v0.5.0
- Framework stubs (CrewAI, AutoGen, DSPy, Guardrails.ai, NeMo) not yet implemented

## v0.3.0 (hypothetical previous)

Would have contained initial prototypes of core contracts and limited framework support.

## v0.0.1 (hypothetical initial)

Would have contained basic harness concept.
