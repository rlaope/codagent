"""LangChain integration — runtime hooks for chains and agents.

Two integration points:

    make_harness_callback_handler(harness)
        Returns a LangChain BaseCallbackHandler that injects the
        harness system addendum into chat-model start events.

    HarnessRunnable(harness, inner_runnable)
        Wraps any LangChain Runnable so its inputs are augmented with
        the harness addendum and outputs are validated.

Optional dependency — install with:

    pip install codagent[langchain]
"""

from __future__ import annotations

from typing import Any

from codagent.harness._harness import Harness


def make_harness_callback_handler(harness: Harness):
    """Build a LangChain callback handler bound to this harness.

    Imports langchain at call time so the rest of codagent does not
    depend on it.
    """
    try:
        from langchain_core.callbacks import BaseCallbackHandler
    except ImportError as e:
        raise ImportError(
            "make_harness_callback_handler requires langchain. "
            "Install: pip install codagent[langchain]"
        ) from e

    addendum = harness.system_addendum()

    class HarnessCallbackHandler(BaseCallbackHandler):
        """Injects harness system addendum into chat-model prompts.

        On chat-model start, prepends a system message (or augments an
        existing one) with the harness addendum.

        On llm end, runs harness.validate against the final generation
        and stores the result on `last_validation`.
        """

        last_validation: dict | None = None

        def on_chat_model_start(  # type: ignore[override]
            self,
            serialized: dict,
            messages: list[list[Any]],
            **kwargs: Any,
        ) -> None:
            for batch in messages:
                if not batch:
                    continue
                first = batch[0]
                role = getattr(first, "type", None) or getattr(first, "role", None)
                if role == "system":
                    first.content = (first.content or "") + "\n\n" + addendum
                else:
                    try:
                        from langchain_core.messages import SystemMessage
                        batch.insert(0, SystemMessage(content=addendum))
                    except Exception:
                        pass

        def on_llm_end(self, response: Any, **kwargs: Any) -> None:
            try:
                text = response.generations[0][0].text
            except Exception:
                return
            self.last_validation = harness.validate(text)

    return HarnessCallbackHandler()


class HarnessRunnable:
    """Wrap any LangChain Runnable with a harness.

    Usage:
        from langchain_openai import ChatOpenAI
        from codagent import Harness, AssumptionSurface
        from codagent.langchain_integration import HarnessRunnable

        chain = HarnessRunnable(
            Harness.compose(AssumptionSurface()),
            ChatOpenAI(model="gpt-4o"),
        )
        chain.invoke([{"role": "user", "content": "..."}])
    """

    def __init__(self, harness: Harness, inner: Any):
        self.harness = harness
        self._inner = inner

    def invoke(self, input_, config=None, **kwargs):
        wrapped = self._wrap(input_)
        return self._inner.invoke(wrapped, config=config, **kwargs)

    async def ainvoke(self, input_, config=None, **kwargs):
        wrapped = self._wrap(input_)
        return await self._inner.ainvoke(wrapped, config=config, **kwargs)

    def _wrap(self, input_):
        if isinstance(input_, list) and input_ and isinstance(input_[0], dict):
            return self.harness.wrap_messages(input_)
        return input_

    def __getattr__(self, item):
        return getattr(self._inner, item)


__all__ = ["make_harness_callback_handler", "HarnessRunnable"]
