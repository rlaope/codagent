"""Adapter: load a markdown rule file (CLAUDE.md, AGENTS.md, .cursor/rules,
.windsurfrules, .clinerules, etc.) and convert it into a Contract.

Source can be:
- Local file path: ``"./CLAUDE.md"`` or absolute
- URL: ``"https://raw.githubusercontent.com/.../CLAUDE.md"``
- GitHub repo shortcut: ``"rlaope/quoted-andrej-karpathy"`` (resolves to
  ``main/CLAUDE.md``)
- GitHub repo + path: ``"rlaope/quoted-andrej-karpathy:AGENTS.md"``

The adapter does not split markdown into per-section contracts — it
treats each markdown file as a single Contract. This is sufficient for
most rule sets and avoids ambiguity in section boundaries.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.request import Request, urlopen

from codagent._abc import Contract, HarnessSource


_GH_SHORT_RE = re.compile(r"^([\w.-]+)/([\w.-]+)(?::(.+))?$")


class _MarkdownContract(Contract):
    def __init__(self, name: str, addendum: str):
        self.name = name
        self._addendum = addendum

    def system_addendum(self) -> str:
        return self._addendum

    def validate(self, response: str) -> tuple[bool, str]:
        return True, ""


class from_markdown(HarnessSource):
    """Load a markdown rule file as a Contract."""

    def __init__(self, source: str, *, branch: str = "main"):
        self.source = source
        self.branch = branch
        self.name = f"markdown:{source}"

    def load(self) -> list[Contract]:
        text = self._fetch().strip()
        if not text:
            return []
        return [_MarkdownContract(name=self.name, addendum=text)]

    def _fetch(self) -> str:
        s = self.source

        # GitHub shortcut: owner/repo or owner/repo:path
        m = _GH_SHORT_RE.match(s)
        if m and not s.startswith(("./", "/", "http")):
            owner, repo, path = m.group(1), m.group(2), m.group(3) or "CLAUDE.md"
            url = f"https://raw.githubusercontent.com/{owner}/{repo}/{self.branch}/{path}"
            return self._fetch_url(url)

        # URL
        if s.startswith(("http://", "https://")):
            return self._fetch_url(s)

        # Local file
        return Path(s).read_text(encoding="utf-8")

    @staticmethod
    def _fetch_url(url: str) -> str:
        req = Request(url, headers={"User-Agent": "codagent"})
        with urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8")
