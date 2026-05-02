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


def _resolve_messages(client):
    messages_obj = getattr(client, "messages", None)
    if messages_obj is None or not hasattr(messages_obj, "create"):
        raise TypeError(
            "client does not look like an Anthropic client "
            "(missing messages.create)"
        )
    return messages_obj


def wrap_anthropic(client, *contracts):
    """Patch an Anthropic client so every messages.create gets the harness addendum.

    Raises ``RuntimeError`` if the client has already been wrapped — call
    :func:`unwrap_anthropic` first to apply a different harness. Mutates
    ``client.messages.create`` in place and returns the client. The patched
    function carries ``_codagent_wrapped`` and ``_codagent_original``
    attributes so the wrap can be safely reversed.
    """
    messages_obj = _resolve_messages(client)
    if getattr(messages_obj.create, "_codagent_wrapped", False):
        raise RuntimeError(
            "Anthropic client is already wrapped by codagent — "
            "call unwrap_anthropic(client) before re-wrapping"
        )

    harness = Harness(list(contracts))
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

    patched._codagent_wrapped = True  # type: ignore[attr-defined]
    patched._codagent_original = original  # type: ignore[attr-defined]
    messages_obj.create = patched
    return client


def unwrap_anthropic(client):
    """Restore the original ``messages.create`` on a wrapped client.

    No-op if the client was not wrapped by codagent. Returns the client
    unchanged so it composes with builder patterns.
    """
    messages_obj = _resolve_messages(client)
    original = getattr(messages_obj.create, "_codagent_original", None)
    if original is not None:
        messages_obj.create = original
    return client
