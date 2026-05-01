"""Adapter: wrap an Anthropic Python SDK client (>= 0.30).

Anthropic's Messages API takes a separate ``system`` parameter (string)
rather than a system message in ``messages``. This wrapper appends the
harness addendum to whatever ``system`` the caller passes (or sets it
if absent).

Usage:

    from anthropic import Anthropic
    from codagent.harness import AssumptionSurface, VerificationLoop
    from codagent.integrations import wrap_anthropic

    client = wrap_anthropic(
        Anthropic(),
        AssumptionSurface(min_items=2),
        VerificationLoop(),
    )

    msg = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1024,
        messages=[{"role": "user", "content": "Add an export feature"}],
    )
"""

from __future__ import annotations

from codagent.harness._harness import Harness


def wrap_anthropic(client, *contracts):
    """Patch an Anthropic client so every messages.create gets the harness addendum.

    Mutates ``client.messages.create`` in place and returns the client.
    """
    harness = Harness(list(contracts))
    messages_obj = getattr(client, "messages", None)
    if messages_obj is None or not hasattr(messages_obj, "create"):
        raise TypeError(
            "client does not look like an Anthropic client "
            "(missing messages.create)"
        )

    original = messages_obj.create
    addendum = harness.system_addendum()

    def patched(*args, **kwargs):
        existing = kwargs.get("system") or ""
        if isinstance(existing, list):
            # Anthropic accepts a list of system content blocks.
            kwargs["system"] = list(existing) + [{"type": "text", "text": addendum}]
        else:
            kwargs["system"] = (existing + ("\n\n" if existing else "") + addendum).strip()
        return original(*args, **kwargs)

    messages_obj.create = patched
    return client
