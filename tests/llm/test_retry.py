"""Tests for LLM Gateway retry logic: exponential backoff, rate limit detection."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from harnessgenj_dev.llm.gateway import (
    DEFAULT_RETRY_BASE_DELAY,
    DEFAULT_RETRY_MAX_ATTEMPTS,
    LLMGateway,
    _calculate_backoff_delay,
    _extract_retry_after,
    _is_retryable_error,
    _with_retry,
)
from harnessgenj_dev.llm.models import LLMResponse, UsageReport


# --- Error Detection Tests ---

class TestIsRetryableError:
    """Test retryable error detection."""

    @pytest.mark.parametrize("error_msg", [
        "429 Too Many Requests",
        "Rate limit exceeded",
        "rate limit hit",
        "Too many requests, please slow down",
        "500 Internal Server Error",
        "502 Bad Gateway",
        "503 Service Unavailable",
        "504 Gateway Timeout",
        "Connection reset by peer",
        "Connection refused",
        "Connection timed out",
        "Request timed out",
        "Timeout error",
        "Server error occurred",
    ])
    def test_retryable_errors(self, error_msg):
        """Test that known retryable errors are detected."""
        exc = Exception(error_msg)
        assert _is_retryable_error(exc) is True

    @pytest.mark.parametrize("error_msg", [
        "400 Bad Request",
        "401 Unauthorized",
        "403 Forbidden",
        "404 Not Found",
        "Invalid API key",
        "Model not found",
        "SyntaxError in code",
        "Some random error",
    ])
    def test_non_retryable_errors(self, error_msg):
        """Test that non-retryable errors fail immediately."""
        exc = Exception(error_msg)
        assert _is_retryable_error(exc) is False


# --- Retry-After Extraction Tests ---

class TestExtractRetryAfter:
    """Test Retry-After header extraction."""

    def test_no_retry_after(self):
        """Test returns None when no retry-after info."""
        exc = Exception("rate limit")
        assert _extract_retry_after(exc) is None

    def test_retry_after_attribute(self):
        """Test extracting retry_after from exception attribute."""
        class RetryableError(Exception):
            def __init__(self, msg, retry_after=None):
                super().__init__(msg)
                self.retry_after = retry_after

        exc = RetryableError("rate limited", retry_after=5.0)
        assert _extract_retry_after(exc) == 5.0

    def test_retry_after_integer(self):
        """Test extracting integer retry-after value."""
        class RetryableError(Exception):
            retry_after = 10

        exc = RetryableError("rate limited")
        assert _extract_retry_after(exc) == 10.0


# --- Backoff Delay Calculation Tests ---

class TestCalculateBackoffDelay:
    """Test exponential backoff calculation."""

    def test_base_delay_attempt_0(self):
        """Test initial attempt uses base delay."""
        delay = _calculate_backoff_delay(0, 1.0, 60.0, 0.0)
        assert delay == pytest.approx(1.0, abs=0.1)

    def test_exponential_growth(self):
        """Test delay grows exponentially."""
        d0 = _calculate_backoff_delay(0, 1.0, 60.0, 0.0)
        d1 = _calculate_backoff_delay(1, 1.0, 60.0, 0.0)
        d2 = _calculate_backoff_delay(2, 1.0, 60.0, 0.0)

        assert d1 > d0  # 2s > 1s
        assert d2 > d1  # 4s > 2s
        assert d1 == pytest.approx(2.0, abs=0.1)
        assert d2 == pytest.approx(4.0, abs=0.1)

    def test_max_delay_cap(self):
        """Test delay is capped at max_delay."""
        delay = _calculate_backoff_delay(10, 1.0, 60.0, 0.0)  # 2^10 = 1024s
        assert delay == 60.0  # Should be capped

    def test_jitter_adds_variation(self):
        """Test jitter produces different delays."""
        delays = [
            _calculate_backoff_delay(0, 1.0, 60.0, 0.5)
            for _ in range(10)
        ]
        # With 50% jitter, delays should vary
        assert len(set(round(d, 2) for d in delays)) > 1

    def test_minimum_delay(self):
        """Test delay is never below 0.1 seconds."""
        delay = _calculate_backoff_delay(0, 0.01, 60.0, 0.0)
        assert delay >= 0.1


# --- Retry Logic Tests ---

@pytest.mark.asyncio
class TestWithRetry:
    """Test the retry wrapper function."""

    async def test_success_on_first_attempt(self):
        """Test no retries when function succeeds."""
        mock_fn = AsyncMock(return_value="ok")
        result = await _with_retry(mock_fn, max_attempts=3)
        assert result == "ok"
        assert mock_fn.call_count == 1

    async def test_retry_on_rate_limit(self):
        """Test retries on 429 error then succeeds."""
        mock_fn = AsyncMock(
            side_effect=[
                Exception("429 Too Many Requests"),
                Exception("rate limit exceeded"),
                "success",
            ]
        )
        result = await _with_retry(mock_fn, max_attempts=3, base_delay=0.01)
        assert result == "success"
        assert mock_fn.call_count == 3

    async def test_no_retry_on_non_retryable(self):
        """Test non-retryable errors fail immediately."""
        mock_fn = AsyncMock(side_effect=Exception("401 Unauthorized"))
        with pytest.raises(Exception, match="401"):
            await _with_retry(mock_fn, max_attempts=3, base_delay=0.01)
        assert mock_fn.call_count == 1

    async def test_exhausts_all_attempts(self):
        """Test raises after all attempts exhausted."""
        mock_fn = AsyncMock(side_effect=Exception("429 rate limit"))
        with pytest.raises(Exception, match="429"):
            await _with_retry(mock_fn, max_attempts=3, base_delay=0.01)
        assert mock_fn.call_count == 3

    async def test_respects_retry_after(self):
        """Test uses Retry-After header when available."""
        class RateLimitError(Exception):
            retry_after = 0.01  # Very short for testing

        call_count = 0
        async def failing_fn():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RateLimitError("rate limited")
            return "ok"

        result = await _with_retry(failing_fn, max_attempts=3, base_delay=60.0)
        assert result == "ok"
        assert call_count == 2


# --- Gateway Integration Tests ---

@pytest.mark.asyncio
class TestGatewayRetry:
    """Test retry integration in LLMGateway."""

    async def test_default_retry_config(self):
        """Test gateway uses default retry config."""
        gateway = LLMGateway()
        assert gateway.max_retries == DEFAULT_RETRY_MAX_ATTEMPTS
        assert gateway.retry_base_delay == DEFAULT_RETRY_BASE_DELAY

    async def test_custom_retry_config(self):
        """Test gateway accepts custom retry config."""
        gateway = LLMGateway(max_retries=5, retry_base_delay=2.0, retry_max_delay=120.0)
        assert gateway.max_retries == 5
        assert gateway.retry_base_delay == 2.0
        assert gateway.retry_max_delay == 120.0

    async def test_retry_disabled(self):
        """Test retry can be disabled with max_retries=0."""
        gateway = LLMGateway(max_retries=0)
        assert gateway.max_retries == 0

    async def test_chat_retries_on_rate_limit(self):
        """Test chat() retries when provider raises 429."""
        from harnessgenj_dev.llm.providers import MessagesAPIProvider

        gateway = LLMGateway(max_retries=3, retry_base_delay=0.01)

        call_count = 0

        async def mock_chat(self, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("429 Too Many Requests")
            return LLMResponse(content="success", usage=UsageReport())

        with patch.object(MessagesAPIProvider, "chat", mock_chat):
            # Also disable degradation by setting empty fallback
            with patch.object(gateway, "_degrade", side_effect=Exception("degrade blocked")):
                response = await gateway.chat(messages=[{"role": "user", "content": "hi"}])
                assert response.content == "success"
                assert call_count == 3

    async def test_chat_fails_on_non_retryable(self):
        """Test chat() skips retry on non-retryable error (called only once)."""
        from harnessgenj_dev.llm.providers import MessagesAPIProvider

        gateway = LLMGateway(max_retries=3, api_key="fake-key-for-test")

        call_count = 0

        async def mock_auth_error(self, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise Exception("401 Invalid API key")

        # Patch _degrade to avoid hanging, check it was called with the right error
        captured_error = None

        async def capture_degrade(*args, **kwargs):
            nonlocal captured_error
            captured_error = kwargs.get("original_error") or args[5]
            raise args[5]  # Re-raise original error

        with patch.object(MessagesAPIProvider, "chat", mock_auth_error):
            with patch.object(gateway, "_degrade", capture_degrade):
                with pytest.raises(Exception, match="401"):
                    await gateway.chat(messages=[{"role": "user", "content": "hi"}])

        # Non-retryable errors should only be attempted once
        assert call_count == 1
        assert "401" in str(captured_error)


# --- Config Tests ---

class TestRetryConfig:
    """Test retry configuration in AppConfig."""

    def test_config_retry_defaults(self):
        """Test config has default retry values."""
        from harnessgenj_dev.config import AppConfig

        config = AppConfig()
        assert config.llm.max_retries == 3
        assert config.llm.retry_base_delay == 1.0
        assert config.llm.retry_max_delay == 60.0

    def test_config_retry_custom_values(self):
        """Test config accepts custom retry values."""
        from harnessgenj_dev.config import AppConfig

        config = AppConfig()
        config.llm.max_retries = 5
        config.llm.retry_base_delay = 2.0
        assert config.llm.max_retries == 5
        assert config.llm.retry_base_delay == 2.0
