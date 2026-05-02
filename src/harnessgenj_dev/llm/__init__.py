"""LLM Gateway - multi-provider LLM interface."""

from .gateway import (
    DEFAULT_RETRY_BASE_DELAY,
    DEFAULT_RETRY_JITTER,
    DEFAULT_RETRY_MAX_ATTEMPTS,
    DEFAULT_RETRY_MAX_DELAY,
    FALLBACK_CHAIN,
    LLMGateway,
    _calculate_backoff_delay,
    _extract_retry_after,
    _is_retryable_error,
    _with_retry,
)
from .models import LLMResponse, StreamChunk, UsageReport

__all__ = [
    "LLMGateway",
    "FALLBACK_CHAIN",
    "LLMResponse",
    "StreamChunk",
    "UsageReport",
    # Retry configuration
    "DEFAULT_RETRY_MAX_ATTEMPTS",
    "DEFAULT_RETRY_BASE_DELAY",
    "DEFAULT_RETRY_MAX_DELAY",
    "DEFAULT_RETRY_JITTER",
    # Retry utilities (for advanced usage)
    "_with_retry",
    "_is_retryable_error",
    "_extract_retry_after",
    "_calculate_backoff_delay",
]
