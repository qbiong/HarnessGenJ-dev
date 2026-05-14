"""LLM Gateway - unified interface for multiple LLM providers.

Optimized for DeepSeek V4 with 1M context window support
and server-side prefix caching.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import AsyncIterator, Callable
from typing import Any, TypeVar

from .models import LLMResponse, StreamChunk, UsageReport
from .models_registry import estimate_cost as registry_estimate_cost
from .providers import (
    BaseProvider,
    LocalProvider,
    MessagesAPIProvider,
    OpenAIProvider,
    OpenRouterProvider,
)
from .providers.deepseek import DeepSeekProvider

# Built-in provider registry
_PROVIDER_REGISTRY: dict[str, type[BaseProvider]] = {
    "anthropic": MessagesAPIProvider,
    "openai": OpenAIProvider,
    "openrouter": OpenRouterProvider,
    "local": LocalProvider,
    "deepseek": DeepSeekProvider,
    # China providers — use OpenAI-compatible API with custom base_url
    "qwen": OpenAIProvider,
    "zhipu": OpenAIProvider,
    "moonshot": OpenAIProvider,
    "siliconflow": OpenAIProvider,
    "baichuan": OpenAIProvider,
    "minimax": OpenAIProvider,
    "custom": OpenAIProvider,
}

# Provider aliases
_PROVIDER_ALIASES: set[str] = {
    "qwen",
    "zhipu",
    "moonshot",
    "siliconflow",
    "baichuan",
    "minimax",
    "custom",
}

# Fallback chain for degradation
FALLBACK_CHAIN: dict[str, list[tuple[str, str]]] = {
    "deepseek-v4-flash": [
        ("deepseek", "deepseek-v4-pro"),
    ],
    "deepseek-v4-pro": [
        ("deepseek", "deepseek-v4-flash"),
    ],
    "deepseek-chat": [
        ("deepseek", "deepseek-v4-flash"),
    ],
    "deepseek-reasoner": [
        ("deepseek", "deepseek-v4-pro"),
    ],
    "deepseek-coder": [
        ("deepseek", "deepseek-v4-flash"),
    ],
    "claude-sonnet-4-6": [
        ("openai", "gpt-4o-mini"),
        ("openai", "gpt-4o"),
    ],
    "claude-opus-4-6": [
        ("openai", "gpt-4o"),
    ],
    "claude-haiku-4-5-20251001": [
        ("openai", "gpt-4o-mini"),
        ("openai", "gpt-4o"),
    ],
    "gpt-4o": [
        ("openai", "gpt-4o-mini"),
    ],
    "gpt-4o-mini": [],
    # China providers — no cross-provider fallback
    "qwen-max": [],
    "qwen-plus": [],
    "qwen-turbo": [],
    "qwen-coder-plus": [],
    "qwen-long": [],
    "glm-4": [],
    "glm-4-plus": [],
    "glm-4-flash": [],
    "moonshot-v1-8k": [],
    "moonshot-v1-32k": [],
    "moonshot-v1-128k": [],
    "abab6.5s-chat": [],
    "abab6.5g-chat": [],
    "Baichuan4": [],
}


T = TypeVar("T")

DEFAULT_RETRY_MAX_ATTEMPTS = 3
DEFAULT_RETRY_BASE_DELAY = 1.0
DEFAULT_RETRY_MAX_DELAY = 60.0
DEFAULT_RETRY_JITTER = 0.1


def _is_retryable_error(exc: Exception) -> bool:
    """Check if an error is retryable."""
    error_str = str(exc).lower()
    retryable_indicators = [
        "429",
        "rate limit",
        "too many requests",
        "500",
        "502",
        "503",
        "504",
        "connection reset",
        "connection refused",
        "connection timed out",
        "timed out",
        "timeout",
        "server error",
    ]
    return any(indicator in error_str for indicator in retryable_indicators)


def _extract_retry_after(exc: Exception) -> float | None:
    """Extract Retry-After header value from exception if available."""
    for attr in ("retry_after", "Retry-After", "retry_after_seconds"):
        if hasattr(exc, attr):
            try:
                return float(getattr(exc, attr))
            except (ValueError, TypeError):
                continue
    return None


def _calculate_backoff_delay(attempt: int, base_delay: float, max_delay: float, jitter: float) -> float:
    """Calculate exponential backoff delay with jitter."""
    delay = base_delay * (2**attempt)
    jitter_range = delay * jitter
    delay += random.uniform(-jitter_range, jitter_range)
    return min(max(delay, 0.1), max_delay)


async def _with_retry(
    func: Callable[..., Any],
    *args: Any,
    max_attempts: int = DEFAULT_RETRY_MAX_ATTEMPTS,
    base_delay: float = DEFAULT_RETRY_BASE_DELAY,
    max_delay: float = DEFAULT_RETRY_MAX_DELAY,
    jitter: float = DEFAULT_RETRY_JITTER,
    **kwargs: Any,
) -> Any:
    """Execute an async function with exponential backoff retry."""
    last_error: Exception | None = None

    for attempt in range(max_attempts):
        try:
            return await func(*args, **kwargs)
        except Exception as exc:
            last_error = exc
            if not _is_retryable_error(exc):
                raise
            if attempt >= max_attempts - 1:
                break
            retry_after = _extract_retry_after(exc)
            if retry_after is not None:
                delay = min(retry_after, max_delay)
            else:
                delay = _calculate_backoff_delay(attempt, base_delay, max_delay, jitter)
            await asyncio.sleep(delay)

    raise last_error  # type: ignore[misc]


class LLMGateway:
    """Unified gateway for LLM interactions across multiple providers.

    Optimized for DeepSeek V4:
    - 1M context window support
    - Server-side prefix caching (set by DeepSeek, no explicit markers needed)
    - Provider-agnostic design (not tied to Claude-specific features)
    """

    def __init__(
        self,
        provider: str = "deepseek",
        model: str = "deepseek-v4-flash",
        api_key: str = "",
        base_url: str | None = None,
        max_retries: int = DEFAULT_RETRY_MAX_ATTEMPTS,
        retry_base_delay: float = DEFAULT_RETRY_BASE_DELAY,
        retry_max_delay: float = DEFAULT_RETRY_MAX_DELAY,
        max_budget_usd: float | None = None,
    ) -> None:
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay
        self.retry_max_delay = retry_max_delay
        self.max_budget_usd = max_budget_usd
        self._client: Any = None
        self._provider_instance: BaseProvider | None = None
        self._total_usage = UsageReport()
        self._custom_providers: dict[str, BaseProvider] = {}

    def _get_provider(self, provider_name: str, api_key: str = "") -> BaseProvider:
        """Get or create a provider instance."""
        if provider_name in self._custom_providers:
            return self._custom_providers[provider_name]

        provider_cls = _PROVIDER_REGISTRY.get(provider_name)
        if provider_cls is None:
            raise ValueError(f"Unknown provider '{provider_name}'. Available: {', '.join(_PROVIDER_REGISTRY.keys())}. ")
        return provider_cls(api_key=api_key or self.api_key, base_url=self.base_url)

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        stream: bool = False,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        max_thinking_tokens: int | None = None,
    ) -> LLMResponse:
        """Send a chat completion request.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            tools: Optional tool definitions in unified format.
            model: Override default model.
            stream: If True, uses streaming.
            temperature: Sampling temperature.
            max_tokens: Maximum output tokens.
            max_thinking_tokens: Extended thinking tokens (Anthropic only).

        Returns:
            LLMResponse with content, usage, and metadata.
        """
        if self.max_budget_usd is not None:
            current_cost = self._total_usage.estimated_cost
            if current_cost >= self.max_budget_usd:
                return LLMResponse(
                    content="",
                    error=f"Budget exceeded: ${current_cost:.4f} >= ${self.max_budget_usd:.4f}",
                )

        target_model = model or self.model
        provider_name = self.provider

        async def _do_chat() -> LLMResponse:
            provider = self._get_provider(provider_name)
            response = await provider.chat(
                messages=messages,
                model=target_model,
                tools=tools,
                temperature=temperature,
                max_tokens=max_tokens,
                max_thinking_tokens=max_thinking_tokens,
            )
            self._track_usage(response.usage)
            return response

        try:
            if self.max_retries > 0:
                response = await _with_retry(
                    _do_chat,
                    max_attempts=self.max_retries,
                    base_delay=self.retry_base_delay,
                    max_delay=self.retry_max_delay,
                )
            else:
                response = await _do_chat()
            return response
        except Exception as exc:
            return await self._degrade(messages, tools, target_model, temperature, max_tokens, exc)

    async def stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a chat completion response."""
        if self.max_budget_usd is not None:
            current_cost = self._total_usage.estimated_cost
            if current_cost >= self.max_budget_usd:
                yield StreamChunk(
                    content="",
                    error=f"Budget exceeded: ${current_cost:.4f} >= ${self.max_budget_usd:.4f}",
                    done=True,
                )
                return

        target_model = model or self.model
        provider = self._get_provider(self.provider)

        async for chunk in provider.stream(
            messages=messages,
            model=target_model,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            if chunk.usage:
                self._track_usage(chunk.usage)
            yield chunk

    def set_provider(self, provider: str, model: str, api_key: str = "") -> None:
        """Change the default LLM provider."""
        self.provider = provider
        self.model = model
        if api_key:
            self.api_key = api_key
        self._provider_instance = None

    def register_provider(self, name: str, provider: BaseProvider) -> None:
        """Register a custom provider instance."""
        self._custom_providers[name] = provider
        _PROVIDER_REGISTRY[name] = type(provider)

    def _track_usage(self, usage: UsageReport) -> None:
        """Accumulate usage statistics."""
        self._total_usage.input_tokens += usage.input_tokens
        self._total_usage.output_tokens += usage.output_tokens
        self._total_usage.total_tokens += usage.total_tokens
        self._total_usage.estimated_cost += usage.estimated_cost
        self._total_usage.cache_creation_tokens += usage.cache_creation_tokens
        self._total_usage.cache_read_tokens += usage.cache_read_tokens

    async def _degrade(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        model: str,
        temperature: float,
        max_tokens: int,
        original_error: Exception,
    ) -> LLMResponse:
        """Try fallback providers in sequence with retry."""
        fallbacks = FALLBACK_CHAIN.get(model, [])
        if not fallbacks:
            raise original_error

        last_error = original_error
        for fb_provider, fb_model in fallbacks:
            try:
                provider = self._get_provider(fb_provider, api_key=self.api_key)
                # Don't leak base_url across providers (e.g. DeepSeek → OpenAI)
                if fb_provider != self.provider:
                    provider.base_url = None  # use provider default

                async def _do_fallback() -> LLMResponse:
                    response = await provider.chat(
                        messages=messages,
                        model=fb_model,
                        tools=tools,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    self._track_usage(response.usage)
                    return response

                if self.max_retries > 0:
                    response = await _with_retry(
                        _do_fallback,
                        max_attempts=self.max_retries,
                        base_delay=self.retry_base_delay,
                        max_delay=self.retry_max_delay,
                    )
                else:
                    response = await _do_fallback()

                response.finish_reason = f"degraded_from_{model}"
                return response
            except Exception as exc:
                last_error = exc
                continue

        raise last_error

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate the cost for the given token usage.

        Uses the model registry for accurate pricing.
        """
        return registry_estimate_cost(self.model, input_tokens, output_tokens)

    def get_usage_stats(self) -> UsageReport:
        """Get cumulative usage statistics."""
        return self._total_usage

    def reset_usage_stats(self) -> None:
        """Reset cumulative usage statistics."""
        self._total_usage = UsageReport()
