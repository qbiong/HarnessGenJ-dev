"""Messages API provider.

Implements the Messages API format (used by Anthropic Claude,
DeepSeek V4, and other compatible providers).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from ..models import LLMResponse, StreamChunk, UsageReport
from .base import BaseProvider


class MessagesAPIProvider(BaseProvider):
    """Messages API format provider.

    Key features:
    - Separate system parameter
    - Content blocks (text, tool_use, thinking)
    - Extended thinking support
    - Tool use via tool_use blocks
    """

    def __init__(self, api_key: str = "", base_url: str | None = None) -> None:
        """Initialize the Messages API client.

        Args:
            api_key: API key. Falls back to ANTHROPIC_API_KEY env var.
            base_url: Optional base URL override.
        """
        self.api_key = api_key
        self.base_url = base_url
        self._client: Any = None

    @property
    def provider_name(self) -> str:
        return "anthropic"

    def _get_client(self) -> Any:
        """Lazy-init the async client."""
        if self._client is not None:
            return self._client

        try:
            from anthropic import AsyncAnthropic
        except ImportError:
            raise RuntimeError("anthropic SDK not installed.")

        kwargs: dict[str, Any] = {"api_key": self.api_key or None}
        if self.base_url:
            kwargs["base_url"] = self.base_url

        self._client = AsyncAnthropic(**kwargs)
        return self._client

    def _convert_tool_format(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert unified tool format to Messages API tool format.

        Unified: {"name": "...", "description": "...", "parameters": {...}}
        Messages API: {"name": "...", "description": "...", "input_schema": {...}}
        """
        api_tools = []
        for tool in tools:
            api_tools.append({
                "name": tool["name"],
                "description": tool.get("description", ""),
                "input_schema": tool.get("parameters", {"type": "object", "properties": {}}),
            })
        return api_tools

    def _build_usage(self, usage: Any) -> UsageReport:
        """Build UsageReport from API usage object."""
        input_tokens = getattr(usage, "input_tokens", 0)
        output_tokens = getattr(usage, "output_tokens", 0)
        cache_creation = getattr(usage, "cache_creation_input_tokens", 0)
        cache_read = getattr(usage, "cache_read_input_tokens", 0)
        total = input_tokens + output_tokens

        cost_per_m: dict[str, float] = {
            "input": 3.0,
            "output": 15.0,
            "cache_creation": 3.75,
            "cache_read": 0.30,
        }
        regular_input = max(input_tokens - cache_creation - cache_read, 0)
        estimated = (
            regular_input * cost_per_m["input"]
            + output_tokens * cost_per_m["output"]
            + cache_creation * cost_per_m["cache_creation"]
            + cache_read * cost_per_m["cache_read"]
        ) / 1_000_000

        return UsageReport(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total,
            estimated_cost=estimated,
            cache_creation_tokens=cache_creation,
            cache_read_tokens=cache_read,
        )

    def _extract_tool_calls(self, message: Any) -> list[dict[str, Any]]:
        """Extract tool calls from API message."""
        tool_calls = []
        content = getattr(message, "content", [])
        for block in content:
            if getattr(block, "type", None) == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "input": getattr(block, "input", {}),
                })
        return tool_calls

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
        """Non-streaming chat via Messages API.

        Args:
            messages: Message list (role/content format).
            model: Model ID.
            system: System prompt (separate param in Messages API).
            tools: Tool definitions in unified format.
            temperature: Sampling temperature.
            max_tokens: Max output tokens.
            max_thinking_tokens: Extended thinking tokens.

        Returns:
            LLMResponse with content, usage, and optional tool_calls.
        """
        client = self._get_client()

        # Extract system message
        api_messages: list[dict[str, Any]] = []
        for msg in messages:
            role = msg.get("role", "user")
            if role == "system":
                system = msg.get("content", system)
            else:
                api_messages.append(msg)

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": api_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        if max_thinking_tokens is not None:
            kwargs["thinking"] = {"type": "enabled", "budget_tokens": max_thinking_tokens}

        if system:
            kwargs["system"] = system

        if tools:
            kwargs["tools"] = self._convert_tool_format(tools)

        message = await client.messages.create(**kwargs)

        content = ""
        for block in getattr(message, "content", []):
            if getattr(block, "type", None) == "text":
                content += block.text

        tool_calls = self._extract_tool_calls(message)
        finish_reason = "tool_calls" if tool_calls else "stop"

        if getattr(message, "stop_reason", None) == "max_tokens":
            finish_reason = "length"

        usage = self._build_usage(message.usage)

        return LLMResponse(
            content=content,
            usage=usage,
            model=model,
            finish_reason=finish_reason,
            tool_calls=tool_calls,
            raw_response=message,
            error=None,
        )

    async def stream(
        self,
        messages: list[dict[str, Any]],
        model: str,
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> AsyncIterator[StreamChunk]:
        """Streaming chat via Messages API.

        Yields StreamChunk objects with incremental content.
        """
        client = self._get_client()

        api_messages: list[dict[str, Any]] = []
        for msg in messages:
            role = msg.get("role", "user")
            if role == "system":
                system = msg.get("content", system)
            else:
                api_messages.append(msg)

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": api_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        if system:
            kwargs["system"] = system

        if tools:
            kwargs["tools"] = self._convert_tool_format(tools)

        async with client.messages.stream(**kwargs) as stream:
            async for event in stream:
                if hasattr(event, "type") and event.type == "content_block_delta":
                    delta_text = getattr(event.delta, "text", None)
                    if delta_text:
                        yield StreamChunk(content=delta_text, done=False)

            message = await stream.get_final_message()
            usage = self._build_usage(message.usage)
            yield StreamChunk(content=None, done=True, usage=usage, error=None)
