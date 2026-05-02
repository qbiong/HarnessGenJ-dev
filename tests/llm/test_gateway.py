"""Tests for LLM Gateway core functionality."""
import pytest
from harnessgenj_dev.llm.gateway import LLMGateway, _PROVIDER_REGISTRY
from harnessgenj_dev.llm.models import UsageReport


class TestLLMGatewayInit:
    """Test LLMGateway initialization."""

    def test_default_provider(self):
        gw = LLMGateway()
        assert gw.provider == "deepseek"

    def test_default_model(self):
        gw = LLMGateway()
        assert gw.model == "deepseek-v4-flash"

    def test_custom_provider(self):
        gw = LLMGateway(provider="openai")
        assert gw.provider == "openai"

    def test_custom_model(self):
        gw = LLMGateway(model="gpt-4o")
        assert gw.model == "gpt-4o"

    def test_custom_api_key(self):
        gw = LLMGateway(api_key="test-key")
        assert gw.api_key == "test-key"

    def test_custom_base_url(self):
        gw = LLMGateway(base_url="http://proxy:8080")
        assert gw.base_url == "http://proxy:8080"

    def test_retry_config_defaults(self):
        gw = LLMGateway()
        assert gw.max_retries > 0

    def test_retry_config_custom(self):
        gw = LLMGateway(max_retries=5, retry_base_delay=2.0)
        assert gw.max_retries == 5
        assert gw.retry_base_delay == 2.0


class TestProviderRegistry:
    """Test provider registry."""

    def test_anthropic_registered(self):
        assert "anthropic" in _PROVIDER_REGISTRY

    def test_openai_registered(self):
        assert "openai" in _PROVIDER_REGISTRY

    def test_openrouter_registered(self):
        assert "openrouter" in _PROVIDER_REGISTRY

    def test_local_registered(self):
        assert "local" in _PROVIDER_REGISTRY

    def test_unknown_provider_raises(self):
        gw = LLMGateway()
        with pytest.raises(ValueError, match="Unknown provider"):
            gw._get_provider("unknown_provider")


class TestProviderSwitching:
    """Test provider switching."""

    def test_set_provider_openai(self):
        gw = LLMGateway()
        gw.set_provider("openai", "gpt-4o", api_key="key")
        assert gw.provider == "openai"
        assert gw.model == "gpt-4o"
        assert gw.api_key == "key"

    def test_set_provider_clears_instance(self):
        gw = LLMGateway()
        gw._provider_instance = "dummy"
        gw.set_provider("openai", "gpt-4o")
        assert gw._provider_instance is None


class TestUsageTracking:
    """Test usage statistics tracking."""

    def test_initial_usage_zero(self):
        gw = LLMGateway()
        stats = gw.get_usage_stats()
        assert stats.input_tokens == 0
        assert stats.output_tokens == 0
        assert stats.estimated_cost == 0

    def test_track_usage_accumulates(self):
        gw = LLMGateway()
        usage = UsageReport(
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            estimated_cost=0.001,
        )
        gw._track_usage(usage)
        stats = gw.get_usage_stats()
        assert stats.input_tokens == 100
        assert stats.output_tokens == 50
        assert stats.total_tokens == 150
        assert stats.estimated_cost == 0.001

    def test_track_usage_multiple_calls(self):
        gw = LLMGateway()
        u1 = UsageReport(input_tokens=100, output_tokens=50, total_tokens=150, estimated_cost=0.001)
        u2 = UsageReport(input_tokens=200, output_tokens=100, total_tokens=300, estimated_cost=0.003)
        gw._track_usage(u1)
        gw._track_usage(u2)
        stats = gw.get_usage_stats()
        assert stats.input_tokens == 300
        assert stats.output_tokens == 150
        assert stats.total_tokens == 450
        assert abs(stats.estimated_cost - 0.004) < 0.0001

    def test_reset_usage_stats(self):
        gw = LLMGateway()
        usage = UsageReport(input_tokens=100, output_tokens=50, total_tokens=150, estimated_cost=0.001)
        gw._track_usage(usage)
        gw.reset_usage_stats()
        stats = gw.get_usage_stats()
        assert stats.input_tokens == 0
        assert stats.output_tokens == 0
        assert stats.estimated_cost == 0
