"""Target: wrap an OpenAI Python SDK client.

This is a stateful target — instead of writing files, it patches the
client's chat.completions.create to inject the harness system addendum
into every messages array.
"""

from __future__ import annotations

from codagent.harness._abc import ApplyTarget, Contract


def wrap_openai(client, *contracts):
    """Patch an OpenAI client with codagent contracts.

    Usage:
        from openai import OpenAI
        from codagent import AssumptionSurface, VerificationLoop
        from codagent.harness.targets import wrap_openai

        client = wrap_openai(OpenAI(), AssumptionSurface(), VerificationLoop())
        client.chat.completions.create(model="gpt-4o", messages=[...])
    """
    from codagent.harness._harness import Harness

    harness = Harness(list(contracts))
    chat = getattr(client, "chat", None)
    completions = getattr(chat, "completions", None) if chat else None
    if completions is None or not hasattr(completions, "create"):
        raise TypeError(
            "client does not look like an OpenAI client "
            "(missing chat.completions.create)"
        )

    original = completions.create

    def patched(*args, **kwargs):
        if "messages" in kwargs:
            kwargs["messages"] = harness.wrap_messages(kwargs["messages"])
        return original(*args, **kwargs)

    completions.create = patched
    return client


class apply_to_openai(ApplyTarget):
    """Object-oriented form of wrap_openai for use with Harness.apply()."""

    name = "openai_client"

    def __init__(self, client):
        self._client = client

    def apply(self, contracts: list[Contract]) -> None:
        wrap_openai(self._client, *contracts)
