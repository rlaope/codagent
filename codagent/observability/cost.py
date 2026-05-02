"""``CostTracker`` — accumulate input/output tokens, compute USD.

Prices live in ``codagent/observability/prices.json`` (per 1k tokens, USD)
and are loaded on import. Override at runtime via
``update_prices_from_disk(path)`` — useful when a new model ships before a
codagent release, or when an enterprise contract sets custom rates. Unknown
models return cost 0 silently; pass ``prices=`` to a tracker for full
isolation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


def _parse_prices_json(text: str) -> dict[str, tuple[float, float]]:
    """Parse a prices JSON document into the {(input, output)} shape.

    Accepted forms per entry:
        {"input": 0.001, "output": 0.002}
        [0.001, 0.002]
    """
    raw = json.loads(text)
    out: dict[str, tuple[float, float]] = {}
    for model, value in raw.items():
        if isinstance(value, dict):
            out[model] = (float(value["input"]), float(value["output"]))
        else:
            out[model] = (float(value[0]), float(value[1]))
    return out


def _load_default_prices() -> dict[str, tuple[float, float]]:
    try:
        from importlib.resources import files
        text = (files("codagent.observability") / "prices.json").read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError, ImportError):
        path = Path(__file__).parent / "prices.json"
        if not path.exists():
            return {}
        text = path.read_text(encoding="utf-8")
    return _parse_prices_json(text)


# Module-level default registry. Mutated by update_prices_from_disk() so new
# CostTracker instances pick up the overrides; existing instances keep their
# per-instance copy unless they re-read from MODEL_PRICES.
MODEL_PRICES: dict[str, tuple[float, float]] = _load_default_prices()


def update_prices_from_disk(path: str | Path) -> dict[str, tuple[float, float]]:
    """Merge a JSON pricing file into MODEL_PRICES.

    Returns the parsed dict that was merged. New ``CostTracker`` instances
    created after this call will see the updates via the default factory.
    """
    parsed = _parse_prices_json(Path(path).read_text(encoding="utf-8"))
    MODEL_PRICES.update(parsed)
    return parsed


@dataclass
class CostTracker:
    """Aggregate token usage and dollar cost for a session.

    Use as a context manager around graph.invoke or as a long-lived
    tracker that you pass into LLM-call wrappers and update via
    ``record_call``.
    """

    model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0
    prices: dict[str, tuple[float, float]] = field(default_factory=lambda: dict(MODEL_PRICES))

    def __enter__(self) -> "CostTracker":
        return self

    def __exit__(self, *args) -> bool:
        return False

    def record_call(
        self,
        *,
        input_tokens: int = 0,
        output_tokens: int = 0,
        model: str | None = None,
    ) -> None:
        self.calls += 1
        self.input_tokens += int(input_tokens)
        self.output_tokens += int(output_tokens)
        if model and self.model is None:
            self.model = model

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def total_usd(self) -> float:
        if not self.model or self.model not in self.prices:
            return 0.0
        in_price, out_price = self.prices[self.model]
        return (self.input_tokens / 1000) * in_price + (self.output_tokens / 1000) * out_price

    def __repr__(self) -> str:
        return (
            f"CostTracker(model={self.model!r}, calls={self.calls}, "
            f"tokens={self.total_tokens} (in={self.input_tokens}, out={self.output_tokens}), "
            f"usd={self.total_usd:.4f})"
        )
