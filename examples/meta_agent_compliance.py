"""Example: domain agent injected as a harness (MetaAgentContract).

Demonstrates the 'a meta-agent supervises another agent' pattern.
We use a fake judge here for offline testing; in production you'd
plug in any callable that runs an LLM (OpenAI, Anthropic, local).
"""

from codagent import Harness, MetaAgentContract


# A real implementation would call the LLM. This stub looks at the
# RESPONSE: section of the prompt and decides based on whether the
# disclaimer phrase is present in the response itself.
def fake_finance_judge(prompt: str) -> str:
    response_section = prompt.split("RESPONSE:")[-1] if "RESPONSE:" in prompt else ""
    if "not financial advice" in response_section.lower():
        return "COMPLIANT — disclaimer found"
    return "NON-compliant — disclaimer missing"


def main() -> None:
    finance_supervisor = MetaAgentContract(
        name="finance-compliance",
        judge_callable=fake_finance_judge,
        judge_prompt_template=(
            "Check whether the response includes the required disclaimer.\n\n"
            "RESPONSE: {response}\n\n"
            "Reply with COMPLIANT or NON-compliant."
        ),
        compliance_marker="COMPLIANT",
        system_addendum_text=(
            "When discussing investments, always include the disclaimer "
            "'This is not financial advice.'"
        ),
    )

    harness = Harness.compose(finance_supervisor)

    bad_response = "Buy NVDA tomorrow before the open."
    good_response = "NVDA looks promising next quarter (this is not financial advice)."

    print("BAD :", harness.validate(bad_response))
    print("GOOD:", harness.validate(good_response))


if __name__ == "__main__":
    main()
