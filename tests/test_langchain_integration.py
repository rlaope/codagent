"""Tests for codagent.langchain_integration.

These tests do not actually require LangChain to be installed — they
verify the import-error path and the HarnessRunnable wrapping shape
without instantiating real chains.
"""

import pytest

from codagent import AssumptionSurface, Harness


def test_callback_handler_factory_raises_without_langchain(monkeypatch):
    """If langchain_core is not importable, the factory should error clearly."""
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("langchain"):
            raise ImportError("simulated missing langchain")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    from codagent.harness.langchain_integration import make_harness_callback_handler

    h = Harness.compose(AssumptionSurface())
    with pytest.raises(ImportError) as ei:
        make_harness_callback_handler(h)
    assert "codagent[langchain]" in str(ei.value)


def test_harness_runnable_wraps_messages_and_delegates():
    """HarnessRunnable should rewrite list-of-dicts inputs and forward."""
    from codagent.harness.langchain_integration import HarnessRunnable

    captured = {}

    class FakeRunnable:
        def invoke(self, x, config=None):
            captured["x"] = x
            captured["config"] = config
            return "ok"

    h = Harness.compose(AssumptionSurface())
    wrapped = HarnessRunnable(h, FakeRunnable())
    out = wrapped.invoke([{"role": "user", "content": "hi"}])
    assert out == "ok"
    msgs = captured["x"]
    assert msgs[0]["role"] == "system"
    assert "Assumptions:" in msgs[0]["content"]


def test_harness_runnable_passes_through_non_message_inputs():
    from codagent.harness.langchain_integration import HarnessRunnable

    class FakeRunnable:
        def invoke(self, x, config=None):
            return x

    wrapped = HarnessRunnable(Harness.compose(AssumptionSurface()), FakeRunnable())
    assert wrapped.invoke("a string") == "a string"
    assert wrapped.invoke({"some": "dict"}) == {"some": "dict"}
