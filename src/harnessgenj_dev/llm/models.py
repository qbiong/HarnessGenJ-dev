"""Shared data models for LLM interactions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class UsageReport:
    """Token usage and cost report."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: float = 0.0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    thinking_tokens: int = 0  # P3-3: Extended thinking/reasoning tokens


@dataclass
class StreamChunk:
    """A single chunk from a streaming response."""

    content: str | None = None
    done: bool = False
    usage: UsageReport | None = None
    error: str | None = None
    tool_calls: list[dict[str, Any]] | None = None  # P4: Structured tool calls in stream
    reasoning_content: str | None = None  # DeepSeek thinking mode reasoning


@dataclass
class LLMResponse:
    """Response from an LLM call."""

    content: str = ""
    usage: UsageReport = field(default_factory=UsageReport)
    model: str = ""
    finish_reason: str = ""
    raw_response: Any = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    reasoning_content: str | None = None  # DeepSeek V4 thinking mode
