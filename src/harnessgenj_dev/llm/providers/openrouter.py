"""OpenRouter provider.

OpenRouter provides a unified gateway to dozens of LLM models
through an OpenAI-compatible API. This provider reuses the OpenAI
SDK with OpenRouter's base URL and adds model discovery helpers.
"""

from __future__ import annotations

from typing import Any

from .openai import OpenAIProvider

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterProvider(OpenAIProvider):
    """OpenRouter API adapter.

    OpenRouter exposes an OpenAI-compatible interface, so we inherit
    from OpenAIProvider and only override the base URL and usage parsing
    (OpenRouter returns usage in a slightly different format).
    """

    def __init__(
        self,
        api_key: str = "",
        base_url: str | None = None,
    ) -> None:
        """Initialize OpenRouter client.

        Args:
            api_key: OpenRouter API key. Falls back to OPENROUTER_API_KEY env var.
            base_url: Optional base URL override (for proxies/testing).
        """
        super().__init__(
            api_key=api_key,
            base_url=base_url or OPENROUTER_BASE_URL,
        )

    @property
    def provider_name(self) -> str:
        return "openrouter"

    def _build_usage(self, usage: Any) -> Any:
        """Build UsageReport from OpenRouter usage object.

        OpenRouter uses the same field names as OpenAI for the
        standard fields, so we delegate to the parent implementation.
        """
        # Re-use parent logic — OpenRouter returns prompt_tokens,
        # completion_tokens, total_tokens just like OpenAI.
        from ..models import UsageReport

        input_tokens = getattr(usage, "prompt_tokens", 0)
        output_tokens = getattr(usage, "completion_tokens", 0)
        total = getattr(usage, "total_tokens", input_tokens + output_tokens)

        # Estimate cost — OpenRouter pricing varies by model,
        # so we use a conservative average (per 1M tokens).
        cost_per_m: dict[str, float] = {"input": 1.0, "output": 3.0}
        estimated = (input_tokens * cost_per_m["input"] + output_tokens * cost_per_m["output"]) / 1_000_000

        return UsageReport(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total,
            estimated_cost=estimated,
        )
