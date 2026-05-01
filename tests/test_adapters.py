"""Tests for HarnessSource adapters."""

from pathlib import Path

import pytest

from codagent import Harness
from codagent.adapters import from_markdown


def test_from_markdown_local_file(tmp_path):
    p = tmp_path / "RULES.md"
    p.write_text("# Rule\n\nDo not break things.\n", encoding="utf-8")

    src = from_markdown(str(p))
    contracts = src.load()
    assert len(contracts) == 1
    assert "Do not break things" in contracts[0].system_addendum()


def test_from_markdown_in_harness_compose(tmp_path):
    p = tmp_path / "rules.md"
    p.write_text("rule body", encoding="utf-8")

    h = Harness.compose(from_markdown(str(p)))
    assert len(h.contracts) == 1
    assert h.system_addendum() == "rule body"


def test_from_markdown_empty_file_yields_no_contract(tmp_path):
    p = tmp_path / "empty.md"
    p.write_text("", encoding="utf-8")

    contracts = from_markdown(str(p)).load()
    assert contracts == []


def test_from_markdown_github_shortcut_resolves(monkeypatch):
    """Ensure 'owner/repo' shortcuts produce a raw.githubusercontent.com URL.

    We don't actually hit the network; we monkeypatch _fetch_url and
    capture the URL passed in.
    """
    captured = {}

    def fake_fetch(url):
        captured["url"] = url
        return "fake content"

    monkeypatch.setattr(from_markdown, "_fetch_url", staticmethod(fake_fetch))

    src = from_markdown("rlaope/quoted-andrej-karpathy")
    src.load()
    assert captured["url"].startswith(
        "https://raw.githubusercontent.com/rlaope/quoted-andrej-karpathy/main/CLAUDE.md"
    )


def test_from_markdown_github_shortcut_with_path(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        from_markdown,
        "_fetch_url",
        staticmethod(lambda url: captured.setdefault("url", url) or "x"),
    )
    from_markdown("rlaope/quoted-andrej-karpathy:AGENTS.md").load()
    assert captured["url"].endswith("/main/AGENTS.md")
