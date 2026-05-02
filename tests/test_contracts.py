"""Tests for the new conversational / tool-use / domain contracts."""

from codagent import (
    CitationRequired,
    Harness,
    MetaAgentContract,
    RefusalPattern,
    ToolCallSurface,
)
from codagent.harness import FaithfulnessContract


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


# -- FaithfulnessContract ---------------------------------------------------


def test_faithfulness_skips_when_no_judge():
    c = FaithfulnessContract()
    c.set_context(["doc1: with_retry retries on listed errors"])
    ok, msg = c.validate("Anything here.")
    assert ok
    assert "no judge" in msg


def test_faithfulness_skips_when_no_context():
    c = FaithfulnessContract(judge=lambda p: "FAITHFUL")
    ok, msg = c.validate("Some response.")
    assert ok
    assert "no context" in msg


def test_faithfulness_pass_when_judge_says_faithful():
    seen_prompts = []
    def judge(p):
        seen_prompts.append(p)
        return "FAITHFUL"
    c = FaithfulnessContract(judge=judge)
    c.set_context(["with_retry retries on listed exception types."])
    ok, msg = c.validate("with_retry retries on listed errors.")
    assert ok
    assert msg == ""
    assert "with_retry retries on listed exception types" in seen_prompts[0]
    assert "with_retry retries on listed errors" in seen_prompts[0]


def test_faithfulness_fail_on_unfaithful_verdict():
    c = FaithfulnessContract(
        judge=lambda p: "UNFAITHFUL: claim about ConnectionError not in context"
    )
    c.set_context(["with_retry retries any exception you specify."])
    ok, msg = c.validate("with_retry retries ConnectionError specifically.")
    assert not ok
    assert "ConnectionError" in msg


def test_faithfulness_fail_on_not_faithful_verdict():
    c = FaithfulnessContract(judge=lambda p: "NOT FAITHFUL: invented claim")
    c.set_context(["doc text"])
    ok, _ = c.validate("response")
    assert not ok


def test_faithfulness_fail_on_unclear_verdict():
    c = FaithfulnessContract(judge=lambda p: "I'm not sure honestly")
    c.set_context(["doc text"])
    ok, msg = c.validate("response")
    assert not ok
    assert "unclear" in msg


def test_faithfulness_set_context_accepts_string_or_list():
    c = FaithfulnessContract(judge=lambda p: "FAITHFUL")
    c.set_context("single string context")
    ok, _ = c.validate("response")
    assert ok
    c.set_context(["doc1", "doc2", "doc3"])
    ok, _ = c.validate("response")
    assert ok


def test_faithfulness_set_context_none_clears():
    c = FaithfulnessContract(judge=lambda p: "FAITHFUL")
    c.set_context(["doc"])
    c.set_context(None)
    ok, msg = c.validate("response")
    assert ok
    assert "no context" in msg


def test_faithfulness_with_context_provider():
    docs = ["initial doc"]
    c = FaithfulnessContract(
        judge=lambda p: "FAITHFUL" if "initial" in p else "UNFAITHFUL",
        context_provider=lambda: docs,
    )
    ok, _ = c.validate("response")
    assert ok
    docs[0] = "different doc"
    ok, _ = c.validate("response")
    assert not ok


def test_faithfulness_system_addendum_mentions_grounding():
    c = FaithfulnessContract()
    addendum = c.system_addendum()
    assert "context" in addendum.lower()
    assert "support" in addendum.lower() or "grounded" in addendum.lower()


def test_faithfulness_composes_in_harness():
    judge_calls = []
    def judge(p):
        judge_calls.append(p)
        return "FAITHFUL"
    faith = FaithfulnessContract(judge=judge)
    h = Harness.compose(CitationRequired(min_citations=1), faith)
    faith.set_context(["with_retry retries on listed exceptions."])
    response = "with_retry retries on listed errors [source: nodes.md]."
    result = h.validate(response)
    assert result["all_ok"] is True
    assert result["Faithfulness"]["ok"] is True
    assert len(judge_calls) == 1
