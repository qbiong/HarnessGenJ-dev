"""Model metadata registry with pricing, context windows, and capabilities.

Direct port of OpenCode's model registry pattern:
https://github.com/opencode-ai/opencode/blob/main/internal/llm/models/anthropic.go

Provides a single source of truth for all supported models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ModelInfo:
    """Metadata for a single model."""

    id: str
    provider: str
    name: str
    context_window: int
    max_output: int
    cost_input_per_1m: float
    cost_output_per_1m: float
    cost_input_cached_per_1m: float = 0.0
    cost_output_cached_per_1m: float = 0.0
    supports_tools: bool = True
    supports_streaming: bool = True
    supports_attachments: bool = True


# ============================================================
# DeepSeek V4 models
# Pricing source: https://api-docs.deepseek.com/quick_start/pricing
# ============================================================
DEEPSEEK_V4_MODELS: list[ModelInfo] = [
    ModelInfo(
        id="deepseek-v4-flash",
        provider="deepseek",
        name="DeepSeek V4 Flash",
        context_window=1_000_000,
        max_output=8_000,
        cost_input_per_1m=0.14,
        cost_output_per_1m=0.28,
        cost_input_cached_per_1m=0.028,
        cost_output_cached_per_1m=0.28,
    ),
    ModelInfo(
        id="deepseek-v4-pro",
        provider="deepseek",
        name="DeepSeek V4 Pro",
        context_window=1_000_000,
        max_output=8_000,
        cost_input_per_1m=1.74,
        cost_output_per_1m=3.48,
        cost_input_cached_per_1m=0.145,
        cost_output_cached_per_1m=3.48,
    ),
    ModelInfo(
        id="deepseek-chat",
        provider="deepseek",
        name="DeepSeek Chat (legacy)",
        context_window=1_000_000,
        max_output=8_000,
        cost_input_per_1m=0.14,
        cost_output_per_1m=0.28,
    ),
    ModelInfo(
        id="deepseek-reasoner",
        provider="deepseek",
        name="DeepSeek Reasoner (legacy)",
        context_window=1_000_000,
        max_output=8_000,
        cost_input_per_1m=0.55,
        cost_output_per_1m=2.19,
    ),
    ModelInfo(
        id="deepseek-coder",
        provider="deepseek",
        name="DeepSeek Coder (legacy)",
        context_window=128_000,
        max_output=8_000,
        cost_input_per_1m=0.14,
        cost_output_per_1m=0.28,
    ),
]

# ============================================================
# Anthropic models
# Pricing source: https://anthropic.com/pricing
# ============================================================
ANTHROPIC_MODELS: list[ModelInfo] = [
    ModelInfo(
        id="claude-opus-4-6",
        provider="anthropic",
        name="Claude Opus 4.6",
        context_window=200_000,
        max_output=4096,
        cost_input_per_1m=15.0,
        cost_output_per_1m=75.0,
        cost_input_cached_per_1m=1.50,
        cost_output_cached_per_1m=7.50,
    ),
    ModelInfo(
        id="claude-sonnet-4-6",
        provider="anthropic",
        name="Claude Sonnet 4.6",
        context_window=200_000,
        max_output=4096,
        cost_input_per_1m=3.0,
        cost_output_per_1m=15.0,
        cost_input_cached_per_1m=0.30,
        cost_output_cached_per_1m=1.50,
    ),
    ModelInfo(
        id="claude-haiku-4-5-20251001",
        provider="anthropic",
        name="Claude Haiku 4.5",
        context_window=200_000,
        max_output=4096,
        cost_input_per_1m=0.80,
        cost_output_per_1m=4.0,
        cost_input_cached_per_1m=0.08,
        cost_output_cached_per_1m=0.40,
    ),
]

# ============================================================
# OpenAI models
# Pricing source: https://openai.com/pricing
# ============================================================
OPENAI_MODELS: list[ModelInfo] = [
    ModelInfo(
        id="gpt-4o",
        provider="openai",
        name="GPT-4o",
        context_window=128_000,
        max_output=4096,
        cost_input_per_1m=2.50,
        cost_output_per_1m=10.0,
        cost_input_cached_per_1m=1.25,
    ),
    ModelInfo(
        id="gpt-4o-mini",
        provider="openai",
        name="GPT-4o mini",
        context_window=128_000,
        max_output=4096,
        cost_input_per_1m=0.15,
        cost_output_per_1m=0.60,
        cost_input_cached_per_1m=0.075,
    ),
    ModelInfo(
        id="gpt-4-turbo",
        provider="openai",
        name="GPT-4 Turbo",
        context_window=128_000,
        max_output=4096,
        cost_input_per_1m=10.0,
        cost_output_per_1m=30.0,
    ),
    ModelInfo(
        id="o1",
        provider="openai",
        name="o1",
        context_window=200_000,
        max_output=4096,
        cost_input_per_1m=15.0,
        cost_output_per_1m=60.0,
    ),
    ModelInfo(
        id="o1-mini",
        provider="openai",
        name="o1 mini",
        context_window=128_000,
        max_output=4096,
        cost_input_per_1m=3.0,
        cost_output_per_1m=12.0,
    ),
]

# ============================================================
# China provider models
# ============================================================
CHINA_MODELS: list[ModelInfo] = [
    ModelInfo(
        id="qwen-max",
        provider="qwen",
        name="Qwen Max",
        context_window=128_000,
        max_output=4096,
        cost_input_per_1m=2.0,
        cost_output_per_1m=6.0,
    ),
    ModelInfo(
        id="qwen-plus",
        provider="qwen",
        name="Qwen Plus",
        context_window=128_000,
        max_output=4096,
        cost_input_per_1m=0.80,
        cost_output_per_1m=2.0,
    ),
    ModelInfo(
        id="qwen-turbo",
        provider="qwen",
        name="Qwen Turbo",
        context_window=128_000,
        max_output=4096,
        cost_input_per_1m=0.30,
        cost_output_per_1m=0.60,
    ),
    ModelInfo(
        id="glm-4-plus",
        provider="zhipu",
        name="GLM-4 Plus",
        context_window=128_000,
        max_output=4096,
        cost_input_per_1m=5.0,
        cost_output_per_1m=5.0,
    ),
    ModelInfo(
        id="Moonshot-v1-32k",
        provider="moonshot",
        name="Moonshot v1 32K",
        context_window=32_000,
        max_output=4096,
        cost_input_per_1m=1.0,
        cost_output_per_1m=1.0,
    ),
]

# ============================================================
# Combined registry
# ============================================================
ALL_MODELS: list[ModelInfo] = (
    DEEPSEEK_V4_MODELS
    + ANTHROPIC_MODELS
    + OPENAI_MODELS
    + CHINA_MODELS
)

_MODEL_MAP: dict[str, ModelInfo] = {m.id: m for m in ALL_MODELS}


def get_model(model_id: str) -> Optional[ModelInfo]:
    """Look up model metadata by ID."""
    return _MODEL_MAP.get(model_id)


def get_provider_models(provider: str) -> list[ModelInfo]:
    """Get all models for a given provider."""
    return [m for m in ALL_MODELS if m.provider == provider]


def estimate_cost(model_id: str, input_tokens: int, output_tokens: int, cached_input: int = 0) -> float:
    """Estimate cost in USD for a model call.

    Args:
        model_id: Model identifier.
        input_tokens: Input token count.
        output_tokens: Output token count.
        cached_input: Cached input token count.

    Returns:
        Estimated cost in USD.
    """
    model = get_model(model_id)
    if model is None:
        return 0.0
    regular_input = max(input_tokens - cached_input, 0)
    return (
        regular_input * model.cost_input_per_1m
        + cached_input * model.cost_input_cached_per_1m
        + output_tokens * model.cost_output_per_1m
    ) / 1_000_000


def get_context_window(model_id: str) -> int:
    """Get the context window size for a model."""
    model = get_model(model_id)
    if model is None:
        return 128_000  # safe default
    return model.context_window


def get_max_output(model_id: str) -> int:
    """Get the default max output tokens for a model."""
    model = get_model(model_id)
    if model is None:
        return 4096
    return model.max_output
