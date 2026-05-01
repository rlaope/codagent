"""Tests for codagent.integrations adapters (no real SDKs required)."""

import pytest

from codagent.harness import AssumptionSurface, Harness


# -- pydantic_ai_prompt -----------------------------------------------------


def test_pydantic_ai_prompt_with_base():
    from codagent.integrations import pydantic_ai_prompt

    h = Harness.compose(AssumptionSurface())
    out = pydantic_ai_prompt(h, base="You are a helpful assistant.")
    assert "You are a helpful assistant." in out
    assert "Assumptions:" in out


def test_pydantic_ai_prompt_no_base():
    from codagent.integrations import pydantic_ai_prompt

    h = Harness.compose(AssumptionSurface())
    out = pydantic_ai_prompt(h)
    assert "Assumptions:" in out


def test_pydantic_ai_prompt_empty_harness():
    from codagent.integrations import pydantic_ai_prompt

    h = Harness.compose()
    assert pydantic_ai_prompt(h, base="hi") == "hi"
    assert pydantic_ai_prompt(h) == ""


# -- wrap_anthropic ---------------------------------------------------------


class _FakeAnthropicMessages:
    def __init__(self):
        self.captured = None
    def create(self, **kwargs):
        self.captured = kwargs
        return {"content": [{"type": "text", "text": "ok"}]}


class _FakeAnthropic:
    def __init__(self):
        self.messages = _FakeAnthropicMessages()


def test_wrap_anthropic_adds_system_when_absent():
    from codagent.integrations import wrap_anthropic

    client = wrap_anthropic(_FakeAnthropic(), AssumptionSurface())
    client.messages.create(messages=[{"role": "user", "content": "hi"}])
    captured = client.messages.captured
    assert "system" in captured
    assert "Assumptions:" in captured["system"]


def test_wrap_anthropic_appends_to_existing_string_system():
    from codagent.integrations import wrap_anthropic

    client = wrap_anthropic(_FakeAnthropic(), AssumptionSurface())
    client.messages.create(
        system="You are helpful.",
        messages=[{"role": "user", "content": "hi"}],
    )
    captured = client.messages.captured
    assert captured["system"].startswith("You are helpful.")
    assert "Assumptions:" in captured["system"]


def test_wrap_anthropic_appends_to_list_system():
    from codagent.integrations import wrap_anthropic

    client = wrap_anthropic(_FakeAnthropic(), AssumptionSurface())
    client.messages.create(
        system=[{"type": "text", "text": "You are helpful."}],
        messages=[{"role": "user", "content": "hi"}],
    )
    captured = client.messages.captured
    assert isinstance(captured["system"], list)
    assert any("Assumptions:" in (b.get("text", "")) for b in captured["system"])


def test_wrap_anthropic_rejects_non_anthropic_object():
    from codagent.integrations import wrap_anthropic

    class NotAnthropic: pass
    with pytest.raises(TypeError):
        wrap_anthropic(NotAnthropic(), AssumptionSurface())


# -- crewai stub ------------------------------------------------------------


def test_crewai_agent_appends_to_backstory():
    from codagent.integrations.crewai import crewai_agent_with_harness

    class FakeAgent:
        backstory = "I am a researcher."

    agent = FakeAgent()
    h = Harness.compose(AssumptionSurface())
    out = crewai_agent_with_harness(base_agent=agent, harness=h)
    assert "I am a researcher." in out.backstory
    assert "Assumptions:" in out.backstory


# -- autogen stub -----------------------------------------------------------


def test_autogen_appends_to_system_message():
    from codagent.integrations.autogen import autogen_assistant_with_harness

    class FakeAutogenAgent:
        system_message = "You are a worker."
        def update_system_message(self, msg):
            self.system_message = msg

    agent = FakeAutogenAgent()
    h = Harness.compose(AssumptionSurface())
    out = autogen_assistant_with_harness(base=agent, harness=h)
    assert "You are a worker." in out.system_message
    assert "Assumptions:" in out.system_message


# -- dspy stub --------------------------------------------------------------


def test_dspy_wrapper_validates_output():
    from codagent.integrations.dspy import dspy_module_with_harness

    def fake_module(question):
        return "Assumptions:\n- treating users as active only\n\nAnswer: 42"

    h = Harness.compose(AssumptionSurface())
    wrapped = dspy_module_with_harness(fake_module, h)
    result = wrapped("what")
    assert "42" in result
    assert wrapped.last_validation["AssumptionSurface"]["ok"] is True
