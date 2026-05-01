"""Tests for the new conversational / tool-use / domain contracts."""

from codagent import (
    CitationRequired,
    Harness,
    MetaAgentContract,
    RefusalPattern,
    ToolCallSurface,
)


# -- ToolCallSurface --------------------------------------------------------


def test_toolcall_passes_when_no_tool_invoked():
    c = ToolCallSurface()
    ok, _ = c.validate("Here's a direct answer with no tool involved.")
    assert ok


def test_toolcall_fails_when_invoking_without_block():
    c = ToolCallSurface()
    ok, msg = c.validate("I am calling the search_orders tool now.")
    assert not ok
    assert "ToolCall" in msg


def test_toolcall_passes_when_invoking_with_block():
    c = ToolCallSurface()
    response = (
        "ToolCall:\n"
        "  tool: search_orders\n"
        "  why: need recent orders for this customer\n"
        "  expect: 0-3 results\n\n"
        "I am calling the search_orders tool now."
    )
    ok, _ = c.validate(response)
    assert ok


# -- RefusalPattern ---------------------------------------------------------


def test_refusal_passes_when_no_sensitive_keyword():
    c = RefusalPattern(sensitive_keywords=("medical-advice",))
    ok, _ = c.validate("Here's how to bake bread.")
    assert ok


def test_refusal_fails_when_keyword_present_without_block():
    c = RefusalPattern(sensitive_keywords=("medical-advice",))
    ok, msg = c.validate("Here is some medical-advice for you...")
    assert not ok
    assert "Refusal" in msg


def test_refusal_passes_with_block():
    c = RefusalPattern(sensitive_keywords=("medical-advice",))
    response = (
        "Refusal:\n  policy: I cannot provide medical-advice.\n"
        "  alternative: please consult a licensed doctor.\n"
    )
    ok, _ = c.validate(response)
    assert ok


def test_refusal_with_no_keywords_is_vacuous():
    c = RefusalPattern()
    ok, _ = c.validate("anything goes")
    assert ok


# -- CitationRequired -------------------------------------------------------


def test_citation_passes_with_marker():
    c = CitationRequired(min_citations=1)
    response = "The drug X reduces Y by 30% [source: Smith 2024]."
    ok, _ = c.validate(response)
    assert ok


def test_citation_fails_without_marker():
    c = CitationRequired(min_citations=1)
    ok, msg = c.validate("The drug X reduces Y by 30%.")
    assert not ok
    assert "citation" in msg


def test_citation_min_count():
    c = CitationRequired(min_citations=3)
    response = "claim1 [source: A]. claim2 [source: B]."
    ok, msg = c.validate(response)
    assert not ok
    assert "2 citation" in msg


# -- MetaAgentContract ------------------------------------------------------


def test_meta_agent_pass():
    captured = {}

    def fake_judge(prompt):
        captured["prompt"] = prompt
        return "Looks fine — COMPLIANT."

    c = MetaAgentContract(
        name="finance-compliance",
        judge_callable=fake_judge,
        judge_prompt_template="Check: {response}",
    )
    ok, _ = c.validate("Some financial advice.")
    assert ok
    assert "Some financial advice." in captured["prompt"]


def test_meta_agent_fail():
    def fake_judge(prompt):
        return "Missing disclaimers, NON-compliant."

    c = MetaAgentContract(
        name="finance-compliance",
        judge_callable=fake_judge,
        judge_prompt_template="Check: {response}",
    )
    ok, msg = c.validate("Buy stock X tomorrow.")
    assert not ok
    assert "missing disclaimers" in msg.lower()


# -- Harness composing all five new contracts -------------------------------


def test_harness_composes_with_all_new_contracts():
    h = Harness.compose(
        ToolCallSurface(),
        RefusalPattern(sensitive_keywords=("legal-advice",)),
        CitationRequired(min_citations=1),
        MetaAgentContract(
            name="judge",
            judge_callable=lambda p: "COMPLIANT",
            judge_prompt_template="{response}",
        ),
    )
    assert len(h.contracts) == 4
    addendum = h.system_addendum()
    assert "ToolCall:" in addendum
    assert "Refusal:" in addendum
    assert "[source:" in addendum
