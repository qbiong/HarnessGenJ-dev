"""DeepSeek V4 provider using OpenAI-compatible API.

DeepSeek API endpoint: https://api.deepseek.com/v1
Uses OpenAI-compatible format for full tool support.
"""

from __future__ import annotations

from typing import Any

from ..models import LLMResponse, UsageReport
from .openai import OpenAIProvider


class DeepSeekProvider(OpenAIProvider):
    """DeepSeek V4 provider via OpenAI-compatible API.

    DeepSeek V4 supports the OpenAI Chat Completions API format,
    providing full tool calling support.
    """

    # Map internal model IDs to DeepSeek API model names
    MODEL_MAP: dict[str, str] = {
        "deepseek-v4-flash": "deepseek-chat",
        "deepseek-v4-pro": "deepseek-chat",
        "deepseek-chat": "deepseek-chat",
        "deepseek-reasoner": "deepseek-reasoner",
        "deepseek-coder": "deepseek-coder",
    }

    @property
    def provider_name(self) -> str:
        return "deepseek"

    def _get_client(self) -> Any:
        """Lazy-init the async client with DeepSeek config."""
        if self._client is not None:
            return self._client

        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise RuntimeError("openai SDK not installed.")

        deepseek_base = self.base_url or "https://api.deepseek.com"
        kwargs: dict[str, Any] = {
            "api_key": self.api_key or "",
            "base_url": deepseek_base.rstrip("/") + "/v1",
        }
        self._client = AsyncOpenAI(**kwargs)
        return self._client

    def _build_usage(self, usage: Any) -> UsageReport:
        """Build UsageReport from DeepSeek usage object."""
        input_tokens = getattr(usage, "prompt_tokens", 0)
        output_tokens = getattr(usage, "completion_tokens", 0)
        total = input_tokens + output_tokens

        cost_input = 0.14
        cost_output = 0.28

        estimated = (input_tokens * cost_input + output_tokens * cost_output) / 1_000_000

        return UsageReport(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total,
            estimated_cost=estimated,
        )

    async def chat(
        self,
        messages: list[dict[str, Any]],
        model: str,
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        max_thinking_tokens: int | None = None,
    ) -> LLMResponse:
        """Non-streaming chat via DeepSeek's OpenAI-compatible API.

        DeepSeek does NOT support extended thinking (parameter ignored).
        Server-side prefix caching is automatic with stable prefixes.
        """
        # Map internal model ID to actual DeepSeek API model name
        api_model = self.MODEL_MAP.get(model, model)
        return await super().chat(
            messages=messages,
            model=api_model,
            system=system,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
            max_thinking_tokens=None,
        )
