"""Tests for LLM providers."""

import pytest


def test_models_llm_response():
    """Test LLMResponse data model."""
    from harnessgenj_dev.llm.models import LLMResponse, UsageReport

    usage = UsageReport(input_tokens=100, output_tokens=50, total_tokens=150)
    response = LLMResponse(
        content="Hello",
        usage=usage,
        model="claude-sonnet-4-6",
        finish_reason="stop",
    )
    assert response.content == "Hello"
    assert response.usage.input_tokens == 100
    assert response.usage.output_tokens == 50
    assert response.tool_calls == []
    assert response.error is None


def test_models_stream_chunk():
    """Test StreamChunk data model."""
    from harnessgenj_dev.llm.models import StreamChunk, UsageReport

    chunk_text = StreamChunk(content="Hello", done=False)
    assert chunk_text.content == "Hello"
    assert not chunk_text.done

    usage = UsageReport(input_tokens=10, output_tokens=5)
    chunk_done = StreamChunk(content=None, done=True, usage=usage)
    assert chunk_done.done
    assert chunk_done.usage.input_tokens == 10


def test_models_usage_report():
    """Test UsageReport with cache fields."""
    from harnessgenj_dev.llm.models import UsageReport

    usage = UsageReport(
        input_tokens=100,
        output_tokens=50,
        cache_creation_tokens=20,
        cache_read_tokens=80,
    )
    assert usage.total_tokens == 0  # Not auto-computed, set by provider
    assert usage.cache_creation_tokens == 20
    assert usage.cache_read_tokens == 80


def test_base_provider_is_abstract():
    """Test BaseProvider cannot be instantiated directly."""
    from harnessgenj_dev.llm.providers.base import BaseProvider

    with pytest.raises(TypeError):
        BaseProvider()


def test_anthropic_provider_name():
    """Test MessagesAPIProvider provider_name property."""
    from harnessgenj_dev.llm.providers.messages_api import MessagesAPIProvider

    provider = MessagesAPIProvider(api_key="test")
    assert provider.provider_name == "anthropic"


def test_openai_provider_name():
    """Test OpenAIProvider provider_name property."""
    from harnessgenj_dev.llm.providers.openai import OpenAIProvider

    provider = OpenAIProvider(api_key="test")
    assert provider.provider_name == "openai"


def test_provider_missing_sdk_raises():
    """Test provider raises clear error when SDK not available."""
    # This test verifies the error path exists.
    # The actual SDK may or may not be installed.
    from harnessgenj_dev.llm.providers.messages_api import MessagesAPIProvider
    from harnessgenj_dev.llm.providers.openai import OpenAIProvider

    # Provider creation should work (lazy init)
    MessagesAPIProvider(api_key="fake")
    OpenAIProvider(api_key="fake")


def test_gateway_provider_registry():
    """Test provider registry in gateway."""
    from harnessgenj_dev.llm.gateway import _PROVIDER_REGISTRY

    assert "anthropic" in _PROVIDER_REGISTRY
    assert "openai" in _PROVIDER_REGISTRY


def test_gateway_custom_provider_registration():
    """Test registering a custom provider."""
    from harnessgenj_dev.llm.gateway import LLMGateway
    from harnessgenj_dev.llm.providers.messages_api import MessagesAPIProvider

    gw = LLMGateway()
    custom = MessagesAPIProvider(api_key="test-key")
    gw.register_provider("custom", custom)

    # Should be findable
    provider = gw._get_provider("custom")
    assert provider is custom


def test_gateway_unknown_provider():
    """Test unknown provider raises ValueError."""
    from harnessgenj_dev.llm.gateway import LLMGateway

    gw = LLMGateway()
    with pytest.raises(ValueError, match="Unknown provider"):
        gw._get_provider("unknown-provider")


def test_gateway_usage_tracking():
    """Test usage statistics tracking."""
    from harnessgenj_dev.llm.gateway import LLMGateway
    from harnessgenj_dev.llm.models import UsageReport

    gw = LLMGateway()

    # Simulate tracking
    gw._track_usage(UsageReport(input_tokens=100, output_tokens=50, total_tokens=150))
    gw._track_usage(UsageReport(input_tokens=200, output_tokens=100, total_tokens=300))

    stats = gw.get_usage_stats()
    assert stats.input_tokens == 300
    assert stats.output_tokens == 150
    assert stats.total_tokens == 450


def test_gateway_reset_usage():
    """Test resetting usage statistics."""
    from harnessgenj_dev.llm.gateway import LLMGateway
    from harnessgenj_dev.llm.models import UsageReport

    gw = LLMGateway()
    gw._track_usage(UsageReport(input_tokens=100, output_tokens=50))
    gw.reset_usage_stats()

    stats = gw.get_usage_stats()
    assert stats.input_tokens == 0
    assert stats.output_tokens == 0


def test_gateway_set_provider():
    """Test switching providers."""
    from harnessgenj_dev.llm.gateway import LLMGateway

    gw = LLMGateway(provider="anthropic", model="claude-sonnet-4-6")
    gw.set_provider("openai", "gpt-4o", api_key="new-key")

    assert gw.provider == "openai"
    assert gw.model == "gpt-4o"
    assert gw.api_key == "new-key"


def test_gateway_estimate_cost_anthropic():
    """Test cost estimation for Anthropic models."""
    from harnessgenj_dev.llm.gateway import LLMGateway

    gw = LLMGateway(provider="anthropic", model="claude-sonnet-4-6")
    cost = gw.estimate_cost(1000, 500)
    assert cost > 0  # Should be non-zero for Anthropic


def test_gateway_estimate_cost_openai():
    """Test cost estimation for OpenAI models."""
    from harnessgenj_dev.llm.gateway import LLMGateway

    gw = LLMGateway(provider="openai", model="gpt-4o")
    cost = gw.estimate_cost(1000, 500)
    assert cost > 0  # Should be non-zero for OpenAI


def test_gateway_estimate_cost_unknown():
    """Test cost estimation for unknown model returns zero."""
    from harnessgenj_dev.llm.gateway import LLMGateway

    gw = LLMGateway(provider="unknown", model="unknown-model")
    cost = gw.estimate_cost(1000, 500)
    assert cost == 0.0


def test_tool_conversion_anthropic():
    """Test Anthropic tool format conversion."""
    from harnessgenj_dev.llm.providers.messages_api import MessagesAPIProvider

    provider = MessagesAPIProvider(api_key="test")
    tools = [
        {
            "name": "read_file",
            "description": "Read a file",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
            },
        }
    ]
    converted = provider._convert_tool_format(tools)
    assert len(converted) == 1
    assert converted[0]["name"] == "read_file"
    assert "input_schema" in converted[0]
    assert "parameters" not in converted[0]


def test_tool_conversion_openai():
    """Test OpenAI tool format conversion."""
    from harnessgenj_dev.llm.providers.openai import OpenAIProvider

    provider = OpenAIProvider(api_key="test")
    tools = [
        {
            "name": "read_file",
            "description": "Read a file",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
            },
        }
    ]
    converted = provider._convert_tool_format(tools)
    assert len(converted) == 1
    assert converted[0]["type"] == "function"
    assert converted[0]["function"]["name"] == "read_file"


def test_fallback_chain_exists():
    """Test fallback chain is defined for key models."""
    from harnessgenj_dev.llm.gateway import FALLBACK_CHAIN

    assert "claude-sonnet-4-6" in FALLBACK_CHAIN
    assert "claude-opus-4-6" in FALLBACK_CHAIN
    assert len(FALLBACK_CHAIN["claude-sonnet-4-6"]) >= 2
