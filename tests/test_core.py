"""Tests for built-in contracts and Harness composer."""

from codagent import AssumptionSurface, VerificationLoop, Harness


def test_assumption_surface_addendum_contains_keyword():
    a = AssumptionSurface()
    assert "Assumptions:" in a.system_addendum()


def test_assumption_surface_validate_pass():
    a = AssumptionSurface(min_items=2)
    response = (
        "Assumptions:\n"
        "- Treating 'users' as active only\n"
        "- Using JSON format\n\n"
        "Here is the rest of the answer."
    )
    ok, msg = a.validate(response)
    assert ok, msg


def test_assumption_surface_validate_fail_no_heading():
    a = AssumptionSurface()
    ok, msg = a.validate("Just here is my answer with no assumptions block.")
    assert not ok
    assert "heading" in msg.lower()


def test_assumption_surface_validate_fail_too_few_items():
    a = AssumptionSurface(min_items=3)
    response = "Assumptions:\n- Only one item\n"
    ok, msg = a.validate(response)
    assert not ok
    assert "items" in msg.lower()


def test_verification_loop_addendum_warns_against_should_work():
    v = VerificationLoop()
    assert "should work" in v.system_addendum()


def test_verification_loop_validate_pass_test_output():
    v = VerificationLoop()
    response = "All tests passed.\n\n$ pnpm test\n  ✓ ok (5ms)"
    ok, _ = v.validate(response)
    assert ok


def test_verification_loop_validate_pass_pytest_passed():
    v = VerificationLoop()
    response = "Done. pytest passed."
    ok, _ = v.validate(response)
    assert ok, "evidence regex should match common 'pytest passed' phrasing"


def test_verification_loop_validate_fail_unbacked():
    v = VerificationLoop()
    ok, msg = v.validate("Should work now.")
    assert not ok
    assert "unbacked" in msg.lower()


def test_verification_loop_validate_pass_with_honest_admission():
    v = VerificationLoop()
    response = "I have not verified this. Specifically: no test runner installed."
    ok, _ = v.validate(response)
    assert ok


def test_harness_wrap_messages_creates_system_when_absent():
    h = Harness.compose(AssumptionSurface(), VerificationLoop())
    messages = [{"role": "user", "content": "hi"}]
    wrapped = h.wrap_messages(messages)
    assert wrapped[0]["role"] == "system"
    assert "Assumptions:" in wrapped[0]["content"]
    assert "should work" in wrapped[0]["content"]
    assert wrapped[1] == messages[0]


def test_harness_wrap_messages_appends_to_existing_system():
    h = Harness.compose(AssumptionSurface())
    messages = [
        {"role": "system", "content": "you are a helpful assistant"},
        {"role": "user", "content": "hi"},
    ]
    wrapped = h.wrap_messages(messages)
    assert len(wrapped) == 2
    assert wrapped[0]["role"] == "system"
    assert "helpful assistant" in wrapped[0]["content"]
    assert "Assumptions:" in wrapped[0]["content"]


def test_harness_validate_aggregates():
    h = Harness.compose(AssumptionSurface(), VerificationLoop())
    response = (
        "Assumptions:\n- A\n- B\n\n"
        "Tests passed: $ npm test\n  ✓ ok"
    )
    out = h.validate(response)
    assert out["all_ok"] is True
    assert out["AssumptionSurface"]["ok"] is True
    assert out["VerificationLoop"]["ok"] is True


def test_compose_rejects_non_contract_non_source():
    import pytest
    with pytest.raises(TypeError):
        Harness.compose("just a string")
