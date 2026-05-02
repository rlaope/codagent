"""Target: wrap an OpenAI Python SDK client.

This is a stateful target — instead of writing files, it patches the
client's chat.completions.create to inject the harness system addendum
into every messages array.
"""

from __future__ import annotations

from codagent.harness._abc import ApplyTarget, Contract


def _resolve_completions(client):
    chat = getattr(client, "chat", None)
    completions = getattr(chat, "completions", None) if chat else None
    if completions is None or not hasattr(completions, "create"):
        raise TypeError(
            "client does not look like an OpenAI client "
            "(missing chat.completions.create)"
        )
    return completions


def wrap_openai(client, *contracts):
    """Patch an OpenAI client with codagent contracts.

    Raises ``RuntimeError`` if the client has already been wrapped — call
    :func:`unwrap_openai` first to apply a different harness. The patched
    function carries ``_codagent_wrapped`` and ``_codagent_original``
    attributes so the wrap can be safely reversed.

    Usage:
        from openai import OpenAI
        from codagent import AssumptionSurface, VerificationLoop
        from codagent.harness.targets import wrap_openai

        client = wrap_openai(OpenAI(), AssumptionSurface(), VerificationLoop())
        client.chat.completions.create(model="gpt-4o", messages=[...])
    """
    from codagent.harness._harness import Harness

    completions = _resolve_completions(client)
    if getattr(completions.create, "_codagent_wrapped", False):
        raise RuntimeError(
            "OpenAI client is already wrapped by codagent — "
            "call unwrap_openai(client) before re-wrapping"
        )

    harness = Harness(list(contracts))
    original = completions.create

    def patched(*args, **kwargs):
        if "messages" in kwargs:
            kwargs["messages"] = harness.wrap_messages(kwargs["messages"])
        return original(*args, **kwargs)

    patched._codagent_wrapped = True  # type: ignore[attr-defined]
    patched._codagent_original = original  # type: ignore[attr-defined]
    completions.create = patched
    return client


def unwrap_openai(client):
    """Restore the original ``chat.completions.create`` on a wrapped client.

    No-op if the client was not wrapped by codagent. Returns the client
    unchanged so it composes with builder patterns.
    """
    completions = _resolve_completions(client)
    original = getattr(completions.create, "_codagent_original", None)
    if original is not None:
        completions.create = original
    return client


class apply_to_openai(ApplyTarget):
    """Object-oriented form of wrap_openai for use with Harness.apply()."""

    name = "openai_client"

    def __init__(self, client):
        self._client = client

    def apply(self, contracts: list[Contract]) -> None:
        wrap_openai(self._client, *contracts)
