"""Tests for the v0.5.x triple PR additions.

1. Judge fallback on regex contracts (i18n / format-variant tolerance)
2. ``update_prices_from_disk`` and JSON-loaded ``MODEL_PRICES``
3. ``unwrap_openai`` / ``unwrap_anthropic`` + double-wrap detection
"""

from __future__ import annotations

import json

import pytest

from codagent.harness import (
    AssumptionSurface,
    CitationRequired,
    RefusalPattern,
    ToolCallSurface,
    VerificationLoop,
)
from codagent.observability import CostTracker, MODEL_PRICES, update_prices_from_disk


# -- 1. Judge fallback ------------------------------------------------------


def _yes_judge(_prompt: str) -> str:
    return "YES"


def _no_judge(_prompt: str) -> str:
    return "NO: missing required block"


def _unclear_judge(_prompt: str) -> str:
    return "I'm not entirely sure"


def test_assumption_regex_pass_skips_judge():
    calls = []

    def judge(p):
        calls.append(p)
        return "NO"

    c = AssumptionSurface(judge=judge)
    ok, _ = c.validate("Assumptions:\n- Treating users as active\n\nAnswer.")
    assert ok
    assert calls == []  # judge never invoked when regex passes


def test_assumption_regex_fail_judge_yes_passes():
    c = AssumptionSurface(judge=_yes_judge)
    # Korean response — regex would fail, judge says YES
    response = "전제:\n- 활성 사용자만 대상\n- JSON 형식 사용\n\n답변..."
    ok, _ = c.validate(response)
    assert ok


def test_assumption_regex_fail_judge_no_fails_with_judge_reason():
    c = AssumptionSurface(judge=_no_judge)
    ok, msg = c.validate("plain answer with no assumptions block at all")
    assert not ok
    assert "judge" in msg


def test_assumption_no_judge_keeps_regex_only():
    c = AssumptionSurface()
    ok, msg = c.validate("plain answer")
    assert not ok
    assert "Assumptions" in msg


def test_assumption_judge_unclear_verdict_fails():
    c = AssumptionSurface(judge=_unclear_judge)
    ok, msg = c.validate("plain answer")
    assert not ok
    assert "unclear" in msg


def test_verification_judge_rescues_non_english_evidence():
    c = VerificationLoop(judge=_yes_judge)
    # Hand-wavy phrase absent and no English evidence markers, but judge passes
    response = "테스트 통과 확인됨: 47개 모두 성공."
    ok, _ = c.validate(response)
    assert ok


def test_verification_unbacked_phrase_still_caught_then_judge_rescues():
    # 'should work' triggers regex fail, but a permissive judge can still pass
    c = VerificationLoop(judge=_yes_judge)
    ok, _ = c.validate("This should work fine. Tests run: 47 passed.")
    assert ok


def test_toolcall_judge_only_runs_when_regex_fails():
    seen = []

    def judge(p):
        seen.append(p)
        return "YES"

    c = ToolCallSurface(judge=judge)
    # No tool invocation hint -> regex passes vacuously, judge skipped
    ok, _ = c.validate("here is a direct answer")
    assert ok
    assert seen == []
    # Tool invoked silently, no ToolCall block -> regex fails, judge consulted
    ok, _ = c.validate("I am calling the search tool now.")
    assert ok
    assert len(seen) == 1


def test_refusal_judge_accepts_localized_refusal_block():
    c = RefusalPattern(
        sensitive_keywords=("medical-advice",),
        judge=_yes_judge,
    )
    response = "거절: medical-advice 정책상 답변 불가. 의사에게 문의하세요."
    ok, _ = c.validate(response)
    assert ok


def test_citation_judge_accepts_localized_marker():
    c = CitationRequired(min_citations=1, judge=_yes_judge)
    ok, _ = c.validate("주장 [출처: Smith 2024].")
    assert ok


# -- 2. Prices JSON --------------------------------------------------------


def test_default_prices_loaded_from_json():
    assert "gpt-4o" in MODEL_PRICES
    assert MODEL_PRICES["gpt-4o"] == (0.0025, 0.010)
    assert "claude-opus-4-5" in MODEL_PRICES


def test_update_prices_from_disk_with_dict_form(tmp_path):
    prices_file = tmp_path / "custom.json"
    prices_file.write_text(
        json.dumps(
            {
                "gpt-5-future": {"input": 0.001, "output": 0.002},
                "enterprise-claude": {"input": 0.0001, "output": 0.0003},
            }
        )
    )
    update_prices_from_disk(prices_file)
    assert MODEL_PRICES["gpt-5-future"] == (0.001, 0.002)
    assert MODEL_PRICES["enterprise-claude"] == (0.0001, 0.0003)


def test_update_prices_from_disk_with_list_form(tmp_path):
    prices_file = tmp_path / "list-form.json"
    prices_file.write_text(json.dumps({"my-model": [0.5, 1.0]}))
    update_prices_from_disk(prices_file)
    assert MODEL_PRICES["my-model"] == (0.5, 1.0)


def test_update_prices_overrides_existing(tmp_path):
    prices_file = tmp_path / "override.json"
    prices_file.write_text(json.dumps({"gpt-4o": {"input": 0.001, "output": 0.002}}))
    original = MODEL_PRICES["gpt-4o"]
    try:
        update_prices_from_disk(prices_file)
        assert MODEL_PRICES["gpt-4o"] == (0.001, 0.002)
        # New tracker picks up the override
        t = CostTracker(model="gpt-4o")
        t.record_call(input_tokens=1000, output_tokens=1000)
        assert abs(t.total_usd - (0.001 + 0.002)) < 1e-9
    finally:
        MODEL_PRICES["gpt-4o"] = original


def test_update_prices_returns_parsed_dict(tmp_path):
    prices_file = tmp_path / "ret.json"
    prices_file.write_text(json.dumps({"x": [0.1, 0.2]}))
    parsed = update_prices_from_disk(prices_file)
    assert parsed == {"x": (0.1, 0.2)}


# -- 3. Wrap / unwrap ------------------------------------------------------


class _FakeOpenAICompletions:
    def __init__(self):
        self.captured = None

    def create(self, **kwargs):
        self.captured = kwargs
        return "ok"


class _FakeOpenAI:
    def __init__(self):
        self.chat = type("Chat", (), {})()
        self.chat.completions = _FakeOpenAICompletions()


class _FakeAnthropicMessages:
    def __init__(self):
        self.captured = None

    def create(self, **kwargs):
        self.captured = kwargs
        return "ok"


class _FakeAnthropic:
    def __init__(self):
        self.messages = _FakeAnthropicMessages()


def test_double_wrap_openai_raises():
    from codagent.integrations import wrap_openai

    client = wrap_openai(_FakeOpenAI(), AssumptionSurface())
    with pytest.raises(RuntimeError, match="already wrapped"):
        wrap_openai(client, AssumptionSurface())


def test_unwrap_openai_restores_original_behavior():
    from codagent.integrations import unwrap_openai, wrap_openai

    client = _FakeOpenAI()
    wrap_openai(client, AssumptionSurface())
    # While wrapped: addendum is injected
    client.chat.completions.create(messages=[{"role": "user", "content": "hi"}])
    msgs_wrapped = client.chat.completions.captured["messages"]
    assert any(m.get("role") == "system" for m in msgs_wrapped)

    unwrap_openai(client)
    # After unwrap: passthrough — no system addendum injection
    client.chat.completions.create(messages=[{"role": "user", "content": "hi"}])
    msgs_unwrapped = client.chat.completions.captured["messages"]
    assert all(m.get("role") != "system" for m in msgs_unwrapped)
    assert not getattr(client.chat.completions.create, "_codagent_wrapped", False)


def test_unwrap_then_rewrap_openai_works():
    from codagent.integrations import unwrap_openai, wrap_openai

    client = wrap_openai(_FakeOpenAI(), AssumptionSurface())
    unwrap_openai(client)
    # Re-wrap with a different harness — should not raise after unwrap
    wrap_openai(client, ToolCallSurface())
    client.chat.completions.create(messages=[{"role": "user", "content": "hi"}])
    captured = client.chat.completions.captured
    assert any("ToolCall" in m.get("content", "") for m in captured["messages"])


def test_unwrap_openai_is_noop_when_never_wrapped():
    from codagent.integrations import unwrap_openai, wrap_openai

    client = _FakeOpenAI()
    unwrap_openai(client)  # must not raise
    # Wrapping after a no-op unwrap still works
    wrap_openai(client, AssumptionSurface())
    client.chat.completions.create(messages=[{"role": "user", "content": "hi"}])
    assert any(m.get("role") == "system" for m in client.chat.completions.captured["messages"])


def test_double_wrap_anthropic_raises():
    from codagent.integrations import wrap_anthropic

    client = wrap_anthropic(_FakeAnthropic(), AssumptionSurface())
    with pytest.raises(RuntimeError, match="already wrapped"):
        wrap_anthropic(client, AssumptionSurface())


def test_unwrap_anthropic_restores_original_behavior():
    from codagent.integrations import unwrap_anthropic, wrap_anthropic

    client = _FakeAnthropic()
    wrap_anthropic(client, AssumptionSurface())
    client.messages.create(messages=[{"role": "user", "content": "hi"}])
    assert "Assumptions" in client.messages.captured["system"]

    unwrap_anthropic(client)
    client.messages.create(messages=[{"role": "user", "content": "hi"}])
    # After unwrap: no system injected
    assert "system" not in client.messages.captured
    assert not getattr(client.messages.create, "_codagent_wrapped", False)


def test_unwrap_then_rewrap_anthropic_works():
    from codagent.integrations import unwrap_anthropic, wrap_anthropic

    client = wrap_anthropic(_FakeAnthropic(), AssumptionSurface())
    unwrap_anthropic(client)
    wrap_anthropic(client, ToolCallSurface())
    client.messages.create(messages=[{"role": "user", "content": "hi"}])
    assert "ToolCall" in client.messages.captured["system"]


def test_unwrap_anthropic_is_noop_when_never_wrapped():
    from codagent.integrations import unwrap_anthropic, wrap_anthropic

    client = _FakeAnthropic()
    unwrap_anthropic(client)  # must not raise
    wrap_anthropic(client, AssumptionSurface())
    client.messages.create(messages=[{"role": "user", "content": "hi"}])
    assert "Assumptions" in client.messages.captured["system"]
