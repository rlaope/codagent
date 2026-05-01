"""Minimal example — no actual API call.

Shows three things:
  1. Compose contracts directly (built-in) and from a markdown file
  2. Inspect the system addendum
  3. Validate a sample response

Run:
    pip install -e .
    python examples/basic.py
"""

from pathlib import Path

from codagent import AssumptionSurface, Harness, VerificationLoop
from codagent.adapters import from_markdown


def main() -> None:
    # 1) Compose harness from built-in contracts and a local markdown file.
    rules_path = Path(__file__).parent / "extra_rules.md"
    rules_path.write_text(
        "# Team conventions\n\n"
        "- All API endpoints must have integration tests.\n"
        "- Migrations must be reversible.\n",
        encoding="utf-8",
    )

    harness = Harness.compose(
        AssumptionSurface(min_items=2),
        VerificationLoop(),
        from_markdown(str(rules_path)),
    )

    print(f"composed harness has {len(harness.contracts)} contract(s)")
    print()

    # 2) Show the system addendum that would be injected.
    user_messages = [{"role": "user", "content": "Add an export feature for users."}]
    wrapped = harness.wrap_messages(user_messages)
    print("=== system message that would be injected ===")
    print(wrapped[0]["content"][:500] + "\n...[truncated]\n")

    # 3) Validate a sample response.
    sample_response = (
        "Assumptions:\n"
        "- Treating 'users' as active only\n"
        "- Using CSV format\n\n"
        "Here is the plan...\n\n"
        "$ pnpm test\n  ✓ all green"
    )
    print("=== validation result ===")
    for k, v in harness.validate(sample_response).items():
        print(f"  {k}: {v}")

    rules_path.unlink()


if __name__ == "__main__":
    main()
