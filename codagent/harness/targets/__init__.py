"""ApplyTarget implementations — write contracts into runtimes.

Built-in:
    apply_to_claude_code     write project CLAUDE.md
    apply_to_cursor          write .cursor/rules/codagent.mdc
    apply_to_copilot         write .github/copilot-instructions.md
    apply_to_agents_md       write AGENTS.md (for Codex / generic agents)
    wrap_openai              patch an OpenAI client at call site
"""

from codagent.harness.targets.agents_md import apply_to_agents_md
from codagent.harness.targets.claude_code import apply_to_claude_code
from codagent.harness.targets.copilot import apply_to_copilot
from codagent.harness.targets.cursor import apply_to_cursor
from codagent.harness.targets.openai_client import wrap_openai

__all__ = [
    "apply_to_agents_md",
    "apply_to_claude_code",
    "apply_to_copilot",
    "apply_to_cursor",
    "wrap_openai",
]
