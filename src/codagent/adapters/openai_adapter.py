"""Adapter for the OpenAI Python SDK (>=1.0).

Wraps a client so every chat.completions.create call has the harness
system addendum injected into its messages array. Original client is
modified in place and returned for chaining.
"""

from __future__ import annotations

from codagent.core import Harness


def wrap_openai(client, *contracts):
    """Patch an OpenAI client with the given codagent contracts.

    Usage:
        from openai import OpenAI
        from codagent import AssumptionSurface, VerificationLoop
        from codagent.adapters import wrap_openai

        client = wrap_openai(OpenAI(), AssumptionSurface(), VerificationLoop())
        client.chat.completions.create(model="gpt-4o", messages=[...])
    """
    harness = Harness(*contracts)
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
        elif args:
            # positional messages not common, fall through
            pass
        return original(*args, **kwargs)

    completions.create = patched
    return client
