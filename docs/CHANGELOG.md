# CHANGELOG

Version history for codagent.

## v0.4.1 (current)

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
