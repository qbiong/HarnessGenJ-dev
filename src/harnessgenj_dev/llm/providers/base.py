"""Base provider interface for LLM backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from ..models import LLMResponse, StreamChunk


class BaseProvider(ABC):
    """Abstract base class for LLM providers.

    All providers (Anthropic, OpenAI, OpenRouter, Ollama) must implement
    this interface. New providers follow OCP — just subclass and register.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return provider identifier, e.g. 'anthropic', 'openai'."""

    @abstractmethod
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
        """Non-streaming chat completion.

        Args:
            messages: OpenAI-style message list.
            model: Model identifier string.
            system: Optional system prompt.
            tools: Optional tool definitions in unified format.
            temperature: Sampling temperature.
            max_tokens: Maximum output tokens.
            max_thinking_tokens: Extended thinking tokens (Anthropic only).

        Returns:
            LLMResponse with content, usage, tool_calls, etc.
        """

    @abstractmethod
    async def stream(
        self,
        messages: list[dict[str, Any]],
        model: str,
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        max_thinking_tokens: int | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Streaming chat completion.

        Args:
            max_thinking_tokens: Extended thinking tokens (Anthropic only).

        Yields:
            StreamChunk objects with incremental content until done=True.
        """
