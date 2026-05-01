"""``CostTracker`` — accumulate input/output tokens, compute USD.

Prices are per 1k tokens, USD, as of late 2025 / early 2026. Update
the table or pass ``prices`` to override per-tracker. Unknown models
return cost 0 silently — explicitly set the model to enable pricing.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# (input_per_1k, output_per_1k) USD
MODEL_PRICES: dict[str, tuple[float, float]] = {
    # OpenAI
    "gpt-4o": (0.0025, 0.010),
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4.1": (0.005, 0.020),
    "o1": (0.015, 0.060),
    "o1-mini": (0.003, 0.012),
    # Anthropic (approximate; verify before relying)
    "claude-opus-4": (0.015, 0.075),
    "claude-opus-4-5": (0.015, 0.075),
    "claude-opus-4-7": (0.015, 0.075),
    "claude-sonnet-4": (0.003, 0.015),
    "claude-sonnet-4-6": (0.003, 0.015),
    "claude-haiku-4": (0.0008, 0.004),
    "claude-haiku-4-5": (0.0008, 0.004),
}


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
