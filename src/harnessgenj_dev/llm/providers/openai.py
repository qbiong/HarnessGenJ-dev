"""OpenAI provider."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from ..models import LLMResponse, StreamChunk, UsageReport
from .base import BaseProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseProvider):
    """OpenAI API adapter.

    Uses the official `openai` SDK with async support.
    Also works with OpenRouter and other OpenAI-compatible APIs.
    """

    def __init__(
        self,
        api_key: str = "",
        base_url: str | None = None,
    ) -> None:
        """Initialize OpenAI client.

        Args:
            api_key: OpenAI API key. Falls back to OPENAI_API_KEY env var.
            base_url: Optional base URL (for OpenRouter, Ollama, proxies).
        """
        self.api_key = api_key
        self.base_url = base_url
        self._client: Any = None

    @property
    def provider_name(self) -> str:
        return "openai"

    def _get_client(self) -> Any:
        """Lazy-init the async OpenAI client."""
        if self._client is not None:
            return self._client

        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise RuntimeError("openai SDK not installed. Run: pip install openai")

        kwargs: dict[str, Any] = {
            "api_key": self.api_key or None,
            "timeout": httpx.Timeout(60.0, connect=15.0, read=120.0, write=30.0),
        }
        if self.base_url:
            kwargs["base_url"] = self.base_url

        self._client = AsyncOpenAI(**kwargs)
        return self._client

    def _convert_tool_format(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert unified tool format to OpenAI format.

        Unified: {"name": "...", "description": "...", "parameters": {...}}
        OpenAI: {"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}
        """
        openai_tools = []
        for tool in tools:
            openai_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get("parameters", {"type": "object", "properties": {}}),
                    },
                }
            )
        return openai_tools

    def _build_usage(self, usage: Any) -> UsageReport:
        """Build UsageReport from OpenAI usage object."""
        input_tokens = getattr(usage, "prompt_tokens", 0)
        output_tokens = getattr(usage, "completion_tokens", 0)
        total = getattr(usage, "total_tokens", input_tokens + output_tokens)

        # Estimate cost (per 1M tokens, GPT-4o pricing)
        cost_per_m: dict[str, float] = {"input": 2.50, "output": 10.0}
        estimated = (input_tokens * cost_per_m["input"] + output_tokens * cost_per_m["output"]) / 1_000_000

        return UsageReport(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total,
            estimated_cost=estimated,
        )

    def _extract_tool_calls(self, choice: Any) -> list[dict[str, Any]]:
        """Extract tool calls from OpenAI choice."""
        tool_calls = []
        message = getattr(choice, "message", None)
        if message is None:
            return tool_calls

        raw_calls = getattr(message, "tool_calls", None)
        if raw_calls:
            for tc in raw_calls:
                import json

                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    logger.warning("Failed to parse tool call arguments: %s", tc.function.arguments)
                    args = {"raw": tc.function.arguments}
                tool_calls.append(
                    {
                        "id": tc.id,
                        "name": tc.function.name,
                        "input": args,
                    }
                )
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
        """Non-streaming chat completion via OpenAI API.

        Args:
            messages: OpenAI-style message list.
            model: Model ID (e.g. 'gpt-4o').
            system: System prompt (injected as system message for OpenAI).
            tools: Tool definitions in unified format.
            temperature: Sampling temperature.
            max_tokens: Max output tokens.
            max_thinking_tokens: Ignored (OpenAI doesn't support extended thinking).

        Returns:
            LLMResponse with content, usage, and optional tool_calls.
        """
        client = self._get_client()

        # Prepend system message if provided separately
        openai_messages: list[dict[str, Any]] = []
        if system:
            openai_messages.append({"role": "system", "content": system})
        for msg in messages:
            if msg.get("role") == "assistant" and msg.get("reasoning_content"):
                # DeepSeek requires reasoning_content to be passed back in thinking mode
                openai_messages.append(msg)
            else:
                cleaned = dict(msg)
                cleaned.pop("reasoning_content", None)
                openai_messages.append(cleaned)

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": openai_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        if tools:
            kwargs["tools"] = self._convert_tool_format(tools)

        response = await client.chat.completions.create(**kwargs)

        choice = response.choices[0]
        content = getattr(choice.message, "content", "") or ""
        reasoning_content = getattr(choice.message, "reasoning_content", None)
        tool_calls = self._extract_tool_calls(choice)
        finish_reason = "tool_calls" if tool_calls else (choice.finish_reason or "stop")

        usage = self._build_usage(response.usage)

        return LLMResponse(
            content=content,
            usage=usage,
            model=model,
            finish_reason=finish_reason,
            tool_calls=tool_calls,
            raw_response=response,
            error=None,
            reasoning_content=reasoning_content,
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
        """Streaming chat completion via OpenAI API.

        Yields StreamChunk objects with incremental content.
        """
        client = self._get_client()

        openai_messages: list[dict[str, Any]] = []
        if system:
            openai_messages.append({"role": "system", "content": system})
        for msg in messages:
            if msg.get("role") == "assistant" and msg.get("reasoning_content"):
                openai_messages.append(msg)
            else:
                cleaned = dict(msg)
                cleaned.pop("reasoning_content", None)
                openai_messages.append(cleaned)

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": openai_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }

        if tools:
            kwargs["tools"] = self._convert_tool_format(tools)

        stream = await client.chat.completions.create(**kwargs)

        async for chunk in stream:
            if chunk.choices:
                delta = chunk.choices[0].delta
                delta_text = getattr(delta, "content", None)

                # Capture tool calls from streaming API (native function calling)
                tool_calls = None
                delta_tc = getattr(delta, "tool_calls", None)
                if delta_tc:
                    tool_calls = []
                    for tc in delta_tc:
                        tc_index = getattr(tc, "index", 0)
                        tc_dict = {
                            "id": tc.id or "",
                            "index": tc_index,
                            "type": tc.type or "function",
                            "function": {
                                "name": tc.function.name if tc.function else "",
                                "arguments": tc.function.arguments if tc.function else "",
                            },
                        }
                        tool_calls.append(tc_dict)

                # Capture reasoning_content (DeepSeek thinking mode)
                delta_reasoning = getattr(delta, "reasoning_content", None)
                if not delta_reasoning:
                    # Some APIs send reasoning_content at chunk level
                    delta_reasoning = getattr(chunk, "reasoning_content", None)

                yield StreamChunk(
                    content=delta_text,
                    done=False,
                    tool_calls=tool_calls,
                    reasoning_content=delta_reasoning,
                )

                # Check for completion
                finish = chunk.choices[0].finish_reason
                if finish:
                    usage = None
                    if hasattr(chunk, "usage") and chunk.usage:
                        usage = self._build_usage(chunk.usage)
                    yield StreamChunk(content=None, done=True, usage=usage, error=None)
                    return

        # If we exit the loop without a finish_reason, yield done anyway
        yield StreamChunk(content=None, done=True, usage=None, error=None)
