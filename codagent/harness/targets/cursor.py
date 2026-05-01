"""Target: write the harness as a Cursor project rule.

Writes ``.cursor/rules/codagent.mdc`` with frontmatter that makes the
rule always-apply.
"""

from __future__ import annotations

from codagent.harness.targets._file_target import _FileApplyTarget


class apply_to_cursor(_FileApplyTarget):
    relative_path = ".cursor/rules/codagent.mdc"
    file_header = (
        "---\n"
        "description: Behavioral contracts applied via codagent.\n"
        "alwaysApply: true\n"
        "---\n"
        "\n"
        "# codagent — generated rules"
    )
    name = "cursor"
