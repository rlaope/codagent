"""Shared logic for file-writing targets (Claude Code, Cursor, Copilot, AGENTS.md)."""

from __future__ import annotations

from pathlib import Path

from codagent.harness._abc import ApplyTarget, Contract


class _FileApplyTarget(ApplyTarget):
    """Base class for targets that write to a file in the project tree."""

    relative_path: str = ""
    file_header: str = ""

    def __init__(self, project_root: str = ".", *, mode: str = "replace"):
        if mode not in ("replace", "append"):
            raise ValueError(f"mode must be 'replace' or 'append', got {mode!r}")
        self.project_root = Path(project_root).resolve()
        self.mode = mode

    def _full_path(self) -> Path:
        return self.project_root / self.relative_path

    def _render(self, contracts: list[Contract]) -> str:
        body = "\n\n---\n\n".join(c.system_addendum() for c in contracts)
        if self.file_header:
            return f"{self.file_header}\n\n{body}\n"
        return f"{body}\n"

    def apply(self, contracts: list[Contract]) -> None:
        path = self._full_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        rendered = self._render(contracts)

        if self.mode == "append" and path.exists():
            existing = path.read_text(encoding="utf-8").rstrip()
            path.write_text(existing + "\n\n" + rendered, encoding="utf-8")
            return

        if path.exists() and self.mode == "replace":
            backup = path.with_suffix(path.suffix + ".bak")
            backup.write_bytes(path.read_bytes())

        path.write_text(rendered, encoding="utf-8")
