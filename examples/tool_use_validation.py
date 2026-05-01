"""Example: tool-use agent with ToolCallSurface contract.

Shows what a compliant vs non-compliant tool-use response looks like
under the codagent harness.
"""

from codagent import Harness, ToolCallSurface


def main() -> None:
    harness = Harness.compose(ToolCallSurface())

    bad = "I am invoking the search_orders tool with the customer email."
    good = (
        "ToolCall:\n"
        "  tool: search_orders\n"
        "  why: user mentioned 'last order' but no order id; need to find it\n"
        "  expect: 0-3 recent orders for this customer email\n"
        "\n"
        "I am invoking the search_orders tool with the customer email."
    )

    print("BAD (no ToolCall block):", harness.validate(bad))
    print()
    print("GOOD (declares intent first):", harness.validate(good))


if __name__ == "__main__":
    main()
