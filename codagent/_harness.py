"""Harness composer — bundles Contracts from any mix of sources/instances."""

from __future__ import annotations

from codagent._abc import ApplyTarget, Contract, HarnessSource


class Harness:
    """Composed bundle of Contracts.

    Build via `Harness.compose(...)` mixing HarnessSource instances and
    bare Contract instances. Use `wrap_messages()` to inject the system
    addendum into a chat messages array, `validate()` to check a
    response, and `apply(target)` to write the harness to a runtime.
    """

    def __init__(self, contracts: list[Contract]):
        self.contracts = list(contracts)

    @classmethod
    def compose(cls, *items) -> "Harness":
        """Mix HarnessSource instances and Contract instances into one Harness."""
        all_contracts: list[Contract] = []
        for item in items:
            if isinstance(item, HarnessSource):
                all_contracts.extend(item.load())
            elif isinstance(item, Contract):
                all_contracts.append(item)
            else:
                raise TypeError(
                    f"compose expects HarnessSource or Contract, got {type(item).__name__}"
                )
        return cls(all_contracts)

    def system_addendum(self) -> str:
        parts = [c.system_addendum() for c in self.contracts]
        return "\n\n".join(p for p in parts if p)

    def wrap_messages(self, messages: list[dict]) -> list[dict]:
        addendum = self.system_addendum()
        if not addendum:
            return list(messages)
        if messages and messages[0].get("role") == "system":
            head = messages[0]
            new_head = {
                "role": "system",
                "content": (head.get("content") or "") + "\n\n" + addendum,
            }
            return [new_head, *messages[1:]]
        return [{"role": "system", "content": addendum}, *messages]

    def validate(self, response: str) -> dict:
        results: dict = {}
        all_ok = True
        for c in self.contracts:
            ok, msg = c.validate(response)
            results[c.name] = {"ok": ok, "reason": msg}
            if not ok:
                all_ok = False
        results["all_ok"] = all_ok
        return results

    def apply(self, target: ApplyTarget) -> None:
        target.apply(self.contracts)
