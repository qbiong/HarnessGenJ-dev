"""Tests for configuration management."""
from harnessgenj_dev.config import AppConfig, LLMConfig


class TestAppConfig:
    """Test application configuration."""

    def test_create_default_config(self):
        config = AppConfig()
        assert config is not None

    def test_config_has_llm(self):
        config = AppConfig()
        assert hasattr(config, "llm")

    def test_config_has_tools(self):
        config = AppConfig()
        assert hasattr(config, "tools")


class TestLLMConfig:
    """Test LLM configuration."""

    def test_default_provider(self):
        llm = LLMConfig()
        assert llm.provider == "anthropic"

    def test_custom_provider(self):
        llm = LLMConfig(provider="openai")
        assert llm.provider == "openai"

    def test_custom_model(self):
        llm = LLMConfig(model="gpt-4o")
        assert llm.model == "gpt-4o"

    def test_api_key(self):
        llm = LLMConfig(api_key="test-key")
        assert llm.api_key == "test-key"

    def test_temperature(self):
        llm = LLMConfig(temperature=0.5)
        assert llm.temperature == 0.5
