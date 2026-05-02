"""Model routing and fallback logic."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ModelInfo:
    """Information about a supported model."""

    name: str
    provider: str
    input_cost_per_m: float  # per million tokens
    output_cost_per_m: float
    max_tokens: int
    capabilities: list[str]  # e.g. ["coding", "reasoning", "vision"]


# Default model priority list
MODEL_PRIORITY: list[ModelInfo] = [
    ModelInfo("claude-sonnet-4-6", "anthropic", 3.0, 15.0, 200_000, ["coding", "reasoning"]),
    ModelInfo("claude-opus-4-6", "anthropic", 15.0, 75.0, 200_000, ["coding", "reasoning", "review"]),
    ModelInfo("claude-haiku-4-5-20251001", "anthropic", 0.80, 4.0, 200_000, ["coding"]),
    ModelInfo("gpt-4o", "openai", 2.5, 10.0, 128_000, ["coding", "reasoning"]),
    ModelInfo("gpt-4o-mini", "openai", 0.15, 0.60, 128_000, ["coding"]),
]


def select_model(task: str = "coding", budget: float | None = None) -> ModelInfo:
    """Select the best model for the given task and budget."""
    candidates = [m for m in MODEL_PRIORITY if task in m.capabilities]
    if budget is not None:
        candidates = [m for m in candidates if m.output_cost_per_m <= budget * 1_000_000]
    return candidates[0] if candidates else MODEL_PRIORITY[0]
