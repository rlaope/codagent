"""Minimal example — no actual API call, just shows the wrapping shape.

Run:
    pip install -e .
    python examples/basic.py
"""

from codagent import AssumptionSurface, VerificationLoop, Harness


def main() -> None:
    harness = Harness(AssumptionSurface(min_items=3), VerificationLoop())

    user_messages = [
        {"role": "user", "content": "Add an export feature for users."},
    ]
    wrapped = harness.wrap_messages(user_messages)

    print("=== messages that would be sent to the LLM ===")
    for m in wrapped:
        print(f"[{m['role']}]")
        print(m["content"])
        print()

    print("=== example response evaluation ===")
    sample_response = (
        "Assumptions:\n"
        "- Treating 'users' as active only (excluding soft-deleted)\n"
        "- Using CSV format\n"
        "- Admin-only endpoint\n\n"
        "Here is the plan...\n\n"
        "$ pnpm test\n  ✓ all green"
    )
    print(harness.validate(sample_response))


if __name__ == "__main__":
    main()
