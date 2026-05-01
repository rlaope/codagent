"""Adapter stub: DSPy integration.

Requires the ``dspy`` extra:

    pip install codagent[dspy]

Planned shape (v0.5.0):

    import dspy
    from codagent.integrations import dspy_module_with_harness

    program = dspy.ChainOfThought("question -> answer")
    wrapped = dspy_module_with_harness(program, harness)

Currently a placeholder — contributions welcome.
"""

from __future__ import annotations

from codagent.harness._harness import Harness


def dspy_module_with_harness(module, harness: Harness):
    """Wrap a DSPy module so its forward returns are validated.

    Stub: returns a thin wrapper. The real version (v0.5.0) will
    integrate with DSPy's Signature system to inject the harness
    addendum into the module's instructions.
    """
    addendum = harness.system_addendum()

    class _Wrapped:
        def __init__(self, inner):
            self._inner = inner
            self._harness = harness
            self._addendum = addendum

        def __call__(self, *args, **kwargs):
            result = self._inner(*args, **kwargs)
            self.last_validation = self._harness.validate(str(result))
            return result

        def __getattr__(self, item):
            return getattr(self._inner, item)

    return _Wrapped(module)
