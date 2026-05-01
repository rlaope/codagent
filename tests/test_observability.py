"""Tests for codagent.observability."""

import json

import pytest

from codagent.observability import (
    BudgetExceeded,
    CostTracker,
    StateTracer,
    StepBudget,
    StepCounter,
)


# -- CostTracker ------------------------------------------------------------


def test_cost_tracker_zero_when_no_calls():
    c = CostTracker()
    assert c.calls == 0
    assert c.total_tokens == 0
    assert c.total_usd == 0.0


def test_cost_tracker_records_and_computes_usd():
    c = CostTracker(model="gpt-4o")
    c.record_call(input_tokens=1000, output_tokens=500)
    c.record_call(input_tokens=500, output_tokens=250)
    assert c.calls == 2
    assert c.input_tokens == 1500
    assert c.output_tokens == 750
    # 1.5k * 0.0025 + 0.75k * 0.010 = 0.00375 + 0.0075 = 0.01125
    assert abs(c.total_usd - 0.01125) < 1e-9


def test_cost_tracker_unknown_model_yields_zero():
    c = CostTracker(model="some-future-model")
    c.record_call(input_tokens=1000, output_tokens=1000)
    assert c.total_usd == 0.0


def test_cost_tracker_context_manager():
    with CostTracker(model="gpt-4o-mini") as c:
        c.record_call(input_tokens=2000, output_tokens=2000)
    assert c.calls == 1
    assert c.total_usd > 0


# -- StepBudget / StepCounter ----------------------------------------------


def test_step_budget_increments():
    b = StepBudget(max_steps=3)
    assert b.step() == 1
    assert b.step() == 2
    assert b.step() == 3
    assert b.remaining() == 0


def test_step_budget_raises_when_exceeded():
    b = StepBudget(max_steps=2)
    b.step()
    b.step()
    with pytest.raises(BudgetExceeded):
        b.step()


def test_step_counter_basic():
    c = StepCounter()
    assert c.increment() == 1
    assert c.increment() == 2
    assert c.count == 2


# -- StateTracer ------------------------------------------------------------


def test_tracer_records_step():
    tracer = StateTracer()

    def node(state):
        return {"answer": "x"}

    wrapped = tracer.wrap_node(node, name="my_step")
    result = wrapped({"q": "hi"})
    assert result == {"answer": "x"}
    assert len(tracer) == 1
    assert tracer.steps[0]["name"] == "my_step"
    assert tracer.steps[0]["before_keys"] == ["q"]
    assert tracer.steps[0]["after_keys"] == ["answer"]
    assert tracer.steps[0]["error"] is None


def test_tracer_records_error():
    tracer = StateTracer()

    def boom(state):
        raise RuntimeError("oops")

    wrapped = tracer.wrap_node(boom, name="boom")
    with pytest.raises(RuntimeError):
        wrapped({})
    assert len(tracer) == 1
    assert tracer.steps[0]["error"] == "RuntimeError"


def test_tracer_to_json():
    tracer = StateTracer()
    tracer.wrap_node(lambda s: {"x": 1}, name="t1")({})
    data = json.loads(tracer.to_json())
    assert isinstance(data, list)
    assert data[0]["name"] == "t1"


def test_tracer_on_step_callback():
    seen = []
    tracer = StateTracer(on_step=seen.append)
    tracer.wrap_node(lambda s: {}, name="cb")({})
    assert len(seen) == 1
    assert seen[0]["name"] == "cb"
