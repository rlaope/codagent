"""codagent — apply OSS LLM-harness ecosystem to code-agent runtimes.

codagent is NOT itself a harness. It is the adapter layer that takes
harnesses (markdown rule sets like CLAUDE.md / AGENTS.md / .cursor/rules,
behavioral specs like Guardrails.ai validators or NeMo Colang flows)
and applies them uniformly to code-agent environments (Claude Code,
Cursor, GitHub Copilot, raw OpenAI/Anthropic clients).

Public API:

    from codagent import Harness
    from codagent.adapters import from_markdown
    from codagent.targets import apply_to_claude_code, apply_to_cursor

    h = Harness.compose(
        from_markdown("https://raw.githubusercontent.com/rlaope/quoted-andrej-karpathy/main/CLAUDE.md"),
        from_markdown("./team/CONVENTIONS.md"),
    )
    h.apply(apply_to_claude_code(project_root="./my-app"))
    h.apply(apply_to_cursor(project_root="./my-app"))

Built-in contract examples (Karpathy-derived):

    from codagent import AssumptionSurface, VerificationLoop
"""

from codagent._abc import ApplyTarget, Contract, HarnessSource
from codagent._harness import Harness
from codagent.builtin import AssumptionSurface, VerificationLoop

__all__ = [
    "ApplyTarget",
    "AssumptionSurface",
    "Contract",
    "Harness",
    "HarnessSource",
    "VerificationLoop",
]
__version__ = "0.1.0"
