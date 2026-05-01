# codagent

[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)

**Apply any OSS LLM-harness to your code-agent runtime.**

`codagent` is the adapter layer between the **harness ecosystem**
(CLAUDE.md / AGENTS.md / `.cursor/rules` / `.windsurfrules` / Guardrails.ai
validators / NeMo Colang flows / custom team conventions) and the
**code-agent runtimes** (Claude Code, Cursor, GitHub Copilot, Codex CLI,
OpenAI / Anthropic clients).

It is **not itself a harness**. It is the layer that lets you take
harnesses written by other people, in other formats, and apply them
uniformly to whatever code agent your team uses.

> Think of it as **ESLint for agent harnesses** — many rule providers,
> one engine, one config.

## Why this exists

The 2025-2026 OSS ecosystem has many LLM-behavior rule sets:

- Markdown gudes: `forrestchang/andrej-karpathy-skills`,
  `rlaope/quoted-andrej-karpathy`, custom team CLAUDE.md files
- Validator libraries: Guardrails.ai, NVIDIA NeMo Guardrails
- Constitutional AI principles, audit checklists, scope contracts

But they all live in different formats, and code agents (Claude Code,
Cursor, Copilot, Aider, Codex) each read different files. Today there
is no clean way to:

1. **Compose** rules from multiple sources
2. **Apply** them uniformly across all code agents
3. **Switch** between rule sources without rewriting your project

`codagent` solves all three.

## Install

```bash
pip install codagent
```

Optional integrations (install only what you need):

```bash
pip install codagent[openai]         # OpenAI client wrapper
pip install codagent[anthropic]      # Anthropic client wrapper (planned)
pip install codagent[langgraph]      # LangGraph node factories
pip install codagent[guardrails-ai]  # wrap Guardrails.ai validators
pip install codagent[nemo]           # wrap NeMo Guardrails flows
```

## Quick start — Python

```python
from codagent import Harness
from codagent.adapters import from_markdown
from codagent.targets import apply_to_claude_code, apply_to_cursor, apply_to_copilot

# Compose a harness from multiple sources
harness = Harness.compose(
    from_markdown("rlaope/quoted-andrej-karpathy"),                  # GitHub shortcut
    from_markdown("forrestchang/andrej-karpathy-skills"),            # GitHub shortcut
    from_markdown("./team/CONVENTIONS.md"),                          # local file
)

# Apply to all the code-agent runtimes your team uses
harness.apply(apply_to_claude_code(project_root="./my-app"))
harness.apply(apply_to_cursor(project_root="./my-app"))
harness.apply(apply_to_copilot(project_root="./my-app"))
```

## Quick start — CLI

```bash
codagent install \
  --from rlaope/quoted-andrej-karpathy \
  --from forrestchang/andrej-karpathy-skills \
  --to claude-code \
  --to cursor \
  --to copilot \
  --to agents-md \
  --project ./my-app \
  --mode append
```

Sources accept:
- GitHub shortcut: `owner/repo` (defaults to `main/CLAUDE.md`)
- GitHub with path: `owner/repo:AGENTS.md`
- HTTPS URL
- Local file path

Targets: `claude-code`, `cursor`, `copilot`, `agents-md`.
Modes: `replace` (default, with `.bak` backup) or `append`.

## Built-in contracts

Two reference Karpathy-derived contracts ship in `codagent.builtin`:

- **`AssumptionSurface`** — forces the agent to prepend an
  `Assumptions:` block when the user request is ambiguous.
- **`VerificationLoop`** — forces the agent to attach evidence
  (test/output/diff) before any "done" claim. Bans phrases like
  "should work" / "looks correct".

You can use them on their own, compose them with imported sources, or
ignore them entirely and bring your own.

```python
from codagent import AssumptionSurface, VerificationLoop, Harness
from codagent.targets import wrap_openai
from openai import OpenAI

client = wrap_openai(OpenAI(), AssumptionSurface(min_items=2), VerificationLoop())
client.chat.completions.create(model="gpt-4o", messages=[...])
```

## Architecture

```
HarnessSource (input)         ApplyTarget (output)
─────────────────────         ─────────────────────
from_markdown                 apply_to_claude_code
from_guardrails_ai            apply_to_cursor
from_nemo                     apply_to_copilot
custom Contract               apply_to_agents_md
                              wrap_openai

           \         /
            Harness (compose, validate, apply)
```

Add a new source: subclass `HarnessSource`, return a list of
`Contract`. Add a new target: subclass `ApplyTarget`, write the
contracts wherever your runtime expects them. PRs welcome.

## Status

`v0.1.0` alpha. Core abstracts (Contract / HarnessSource /
ApplyTarget / Harness) are stable in spirit. Adapters and targets
expand over time.

## License

MIT — see [LICENSE](./LICENSE). Inspired by, and links to, the
upstream Karpathy-derived rule sets cited in `LICENSE`.
