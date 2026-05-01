"""Adapter: LlamaIndex callback handler that augments LLM prompts.

Wraps LlamaIndex's CBEventType.LLM event so the harness system addendum
is attached to outgoing prompts.

Optional dependency — install with:

    pip install codagent[llamaindex]
"""

from __future__ import annotations

from codagent.harness._harness import Harness


def HarnessLlamaIndexCallback(harness: Harness):
    """Factory: returns a LlamaIndex BaseCallbackHandler bound to ``harness``.

    Imports llama_index at call time so the rest of codagent does not
    depend on it.
    """
    try:
        from llama_index.core.callbacks.base import BaseCallbackHandler
        from llama_index.core.callbacks.schema import CBEventType, EventPayload
    except ImportError as e:  # pragma: no cover
        raise ImportError(
            "HarnessLlamaIndexCallback requires llama-index. "
            "Install: pip install codagent[llamaindex]"
        ) from e

    addendum = harness.system_addendum()

    class _Handler(BaseCallbackHandler):
        last_validation: dict | None = None

        def __init__(self):
            super().__init__(event_starts_to_ignore=[], event_ends_to_ignore=[])

        def on_event_start(self, event_type, payload=None, event_id="", parent_id="", **kwargs):
            if event_type == CBEventType.LLM and payload:
                # Best-effort: prepend addendum to a system-style key if present.
                messages = payload.get("messages") or []
                if messages and isinstance(messages, list):
                    head = messages[0]
                    if isinstance(head, dict) and head.get("role") == "system":
                        head["content"] = (head.get("content") or "") + "\n\n" + addendum
                    else:
                        messages.insert(0, {"role": "system", "content": addendum})
            return event_id

        def on_event_end(self, event_type, payload=None, event_id="", **kwargs):
            if event_type == CBEventType.LLM and payload:
                response = payload.get(EventPayload.RESPONSE) or payload.get("response")
                if response:
                    self.last_validation = harness.validate(str(response))

        def start_trace(self, trace_id=None):
            pass

        def end_trace(self, trace_id=None, trace_map=None):
            pass

    return _Handler()
