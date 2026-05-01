"""Tests for ApplyTarget implementations (file-writing targets)."""

from pathlib import Path

import pytest

from codagent import AssumptionSurface, Harness, VerificationLoop
from codagent.harness.targets import (
    apply_to_agents_md,
    apply_to_claude_code,
    apply_to_copilot,
    apply_to_cursor,
)


@pytest.fixture
def sample_harness():
    return Harness.compose(AssumptionSurface(min_items=1), VerificationLoop())


def test_apply_to_claude_code_writes_file(tmp_path, sample_harness):
    target = apply_to_claude_code(project_root=str(tmp_path))
    sample_harness.apply(target)

    out = tmp_path / "CLAUDE.md"
    assert out.exists()
    text = out.read_text()
    assert "Assumptions:" in text
    assert "should work" in text  # from VerificationLoop addendum


def test_apply_to_cursor_writes_mdc_with_frontmatter(tmp_path, sample_harness):
    sample_harness.apply(apply_to_cursor(project_root=str(tmp_path)))
    out = tmp_path / ".cursor" / "rules" / "codagent.mdc"
    assert out.exists()
    text = out.read_text()
    assert text.startswith("---\n")
    assert "alwaysApply: true" in text


def test_apply_to_copilot_writes_dot_github(tmp_path, sample_harness):
    sample_harness.apply(apply_to_copilot(project_root=str(tmp_path)))
    out = tmp_path / ".github" / "copilot-instructions.md"
    assert out.exists()


def test_apply_to_agents_md(tmp_path, sample_harness):
    sample_harness.apply(apply_to_agents_md(project_root=str(tmp_path)))
    out = tmp_path / "AGENTS.md"
    assert out.exists()


def test_replace_mode_creates_bak(tmp_path, sample_harness):
    out = tmp_path / "CLAUDE.md"
    out.write_text("PREEXISTING USER NOTES")
    sample_harness.apply(apply_to_claude_code(project_root=str(tmp_path), mode="replace"))
    assert out.read_text() != "PREEXISTING USER NOTES"
    assert (tmp_path / "CLAUDE.md.bak").read_text() == "PREEXISTING USER NOTES"


def test_append_mode_keeps_existing(tmp_path, sample_harness):
    out = tmp_path / "CLAUDE.md"
    out.write_text("PREEXISTING\n")
    sample_harness.apply(apply_to_claude_code(project_root=str(tmp_path), mode="append"))
    text = out.read_text()
    assert text.startswith("PREEXISTING")
    assert "Assumptions:" in text


def test_invalid_mode_raises():
    with pytest.raises(ValueError):
        apply_to_claude_code(mode="overwrite")
