# CLAUDE.md

Behavioral guidelines for working in this repo. Karpathy's rules first, then codagent-specific context.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding
**Don't assume. Don't hide confusion. Surface tradeoffs.**

- State assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First
**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Test: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes
**Touch only what you must. Clean up only your own mess.**

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- Note unrelated dead code; don't delete it unless asked.
- Remove imports/vars/functions YOUR changes orphaned. Pre-existing dead code stays.

Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution
**Define success criteria. Loop until verified.**

- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

Multi-step tasks: state a brief plan with a verify step for each item. Strong success criteria let you loop independently.

## 5. Communication
**Plain words. Settled decisions stay settled. Korean stays formal.**

- **존댓말 only when responding in Korean.** Never default to 반말. If you slip, switch back immediately and apologize once.
- **No jargon dumps.** Don't pile up English technical terms ("primitive", "lock-in", "cancellation 전파", "mount", "boundary") when one plain Korean phrase works. If a term is genuinely necessary, gloss it once in plain Korean and move on.
- **Decided is decided.** When the user has set a direction ("이쪽으로 간다", "셋다처리해"), don't re-litigate, ask them to "verify" / "validate" / "reconsider", or list comparison tables of alternatives. Move forward and ask only the concrete next-step question.
- **Short over structured.** For exploratory or direction questions, 2–3 plain sentences with one tradeoff beats headers + bullets + tables. Reach for structure only when the user asks for a deliverable.
- **One next-step question, not a menu of three** unless the branches are genuinely independent and the user has explicitly invited a choice.

---

## Project context — codagent

Python 3.10–3.13 library of production utilities for LLM agents. Five modules: `nodes`, `tools`, `observability`, `harness`, `integrations`. Core is framework-agnostic; framework adapters in `codagent.integrations` use **lazy/runtime imports** so optional deps never break the core.

- **Test:** `pytest -q` (CI matrix 3.10–3.13 in `.github/workflows/tests.yml`). No lint configured.
- **Hot paths:** `codagent/harness/builtin.py`, `codagent/__init__.py`, `codagent/harness/_abc.py`.
- **Commits:** No `Co-Authored-By: Claude` trailer. Direct-to-main is allowed.

**Conventions to preserve when editing:**

- **Contracts** (`AssumptionSurface`, `VerificationLoop`, `ToolCallSurface`, `RefusalPattern`, `CitationRequired`) are `@dataclass` with an optional `judge: Callable[[str], str]` field. Validation is regex-first; the judge is consulted only when regex fails (i18n / format-variant tolerance, cost bounded by failure rate). Keep that shape when adding new contracts.
- **Client wrappers** (`wrap_openai`, `wrap_anthropic`) mutate the client in place and must stay reversible via `unwrap_*`. Patched callables carry `_codagent_wrapped` and `_codagent_original` — preserve both. Double-wrap raises.
- **Pricing** lives in `codagent/observability/prices.json` (shipped as package data via `[tool.setuptools.package-data]`). Override at runtime with `update_prices_from_disk(path)`; do not hardcode prices in Python.

**Deeper reference:** [README.md](README.md) · [docs/index.md](docs/index.md) · [AGENTS.md](AGENTS.md) · [CONTRIBUTING.md](CONTRIBUTING.md)
