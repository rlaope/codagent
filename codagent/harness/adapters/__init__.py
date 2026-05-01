"""HarnessSource implementations — pull contracts from external places.

Built-in:
    from_markdown        load CLAUDE.md / AGENTS.md / .cursor/rules / etc.
    from_guardrails_ai   wrap a Guardrails.ai validator (extra dep)
    from_nemo            wrap a NeMo Guardrails flow (extra dep)
"""

from codagent.harness.adapters.markdown import from_markdown

__all__ = ["from_markdown"]

# Optional adapters — only available if their extras are installed.
try:
    from codagent.harness.adapters.guardrails_ai import from_guardrails_ai
    __all__.append("from_guardrails_ai")
except Exception:
    pass

try:
    from codagent.harness.adapters.nemo import from_nemo
    __all__.append("from_nemo")
except Exception:
    pass
