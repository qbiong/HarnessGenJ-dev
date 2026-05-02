"""Tests for retry logic in LLM gateway."""
import pytest
from harnessgenj_dev.llm.gateway import (
    _is_retryable_error,
    _extract_retry_after,
    _calculate_backoff_delay,
)


class TestIsRetryableError:
    """Test retryable error detection."""

    def test_rate_limit_429(self):
        assert _is_retryable_error(Exception("429 Too Many Requests"))

    def test_rate_limit_text(self):
        assert _is_retryable_error(Exception("Rate limit exceeded"))

    def test_server_error_500(self):
        assert _is_retryable_error(Exception("500 Internal Server Error"))

    def test_bad_gateway_502(self):
        assert _is_retryable_error(Exception("502 Bad Gateway"))

    def test_service_unavailable_503(self):
        assert _is_retryable_error(Exception("503 Service Unavailable"))

    def test_gateway_timeout_504(self):
        assert _is_retryable_error(Exception("504 Gateway Timeout"))

    def test_connection_reset(self):
        assert _is_retryable_error(Exception("Connection reset by peer"))

    def test_connection_refused(self):
        assert _is_retryable_error(Exception("Connection refused"))

    def test_timeout(self):
        assert _is_retryable_error(Exception("Request timed out"))

    def test_invalid_api_key_not_retryable(self):
        assert not _is_retryable_error(Exception("Invalid API key"))

    def test_model_not_found_not_retryable(self):
        assert not _is_retryable_error(Exception("Model not found"))

    def test_normal_exception_not_retryable(self):
        assert not _is_retryable_error(Exception("Some random error"))


class TestExtractRetryAfter:
    """Test Retry-After header extraction."""

    def test_retry_after_attribute(self):
        class FakeExc(Exception):
            retry_after = 30
        assert _extract_retry_after(FakeExc("rate limited")) == 30.0

    def test_no_retry_after(self):
        assert _extract_retry_after(Exception("no header")) is None

    def test_invalid_retry_after(self):
        class FakeExc(Exception):
            retry_after = "invalid"
        result = _extract_retry_after(FakeExc("bad header"))
        assert result is None


class TestCalculateBackoffDelay:
    """Test exponential backoff calculation."""

    def test_base_delay_first_attempt(self):
        delay = _calculate_backoff_delay(0, 1.0, 60.0, 0.0)
        assert abs(delay - 1.0) < 0.5

    def test_delay_increases_with_attempt(self):
        d1 = _calculate_backoff_delay(0, 1.0, 60.0, 0.0)
        d2 = _calculate_backoff_delay(2, 1.0, 60.0, 0.0)
        assert d2 > d1

    def test_delay_capped_at_max(self):
        delay = _calculate_backoff_delay(10, 1.0, 5.0, 0.0)
        assert delay <= 5.0

    def test_jitter_adds_variance(self):
        delays = [_calculate_backoff_delay(0, 1.0, 60.0, 0.5) for _ in range(10)]
        assert len(set(delays)) > 1
