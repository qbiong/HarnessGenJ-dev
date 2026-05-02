"""Tests for OpenRouter provider."""
from harnessgenj_dev.llm.providers.openrouter import OpenRouterProvider, OPENROUTER_BASE_URL


class TestOpenRouterProviderInit:
    """Test OpenRouterProvider initialization."""

    def test_provider_name(self):
        p = OpenRouterProvider()
        assert p.provider_name == "openrouter"

    def test_default_base_url(self):
        p = OpenRouterProvider()
        assert p.base_url == OPENROUTER_BASE_URL

    def test_custom_api_key(self):
        p = OpenRouterProvider(api_key="test-key")
        assert p.api_key == "test-key"

    def test_custom_base_url_override(self):
        p = OpenRouterProvider(base_url="http://custom")
        assert p.base_url == "http://custom"

    def test_inherits_from_openai(self):
        from harnessgenj_dev.llm.providers.openai import OpenAIProvider
        p = OpenRouterProvider()
        assert isinstance(p, OpenAIProvider)
