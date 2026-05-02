"""Tests for OpenAI provider."""
from harnessgenj_dev.llm.providers.openai import OpenAIProvider


class TestOpenAIProviderInit:
    """Test OpenAIProvider initialization."""

    def test_provider_name(self):
        p = OpenAIProvider()
        assert p.provider_name == "openai"

    def test_custom_api_key(self):
        p = OpenAIProvider(api_key="test-key")
        assert p.api_key == "test-key"

    def test_custom_base_url(self):
        p = OpenAIProvider(base_url="http://proxy:8080")
        assert p.base_url == "http://proxy:8080"

    def test_tool_conversion(self):
        p = OpenAIProvider()
        tools = [{"name": "test", "description": "A test tool", "parameters": {"type": "object"}}]
        result = p._convert_tool_format(tools)
        assert len(result) == 1
        assert result[0]["type"] == "function"
        assert result[0]["function"]["name"] == "test"

    def test_tool_conversion_multiple(self):
        p = OpenAIProvider()
        tools = [
            {"name": "t1", "description": "Tool 1", "parameters": {"type": "object"}},
            {"name": "t2", "description": "Tool 2", "parameters": {"type": "object"}},
        ]
        result = p._convert_tool_format(tools)
        assert len(result) == 2
        assert result[0]["function"]["name"] == "t1"
        assert result[1]["function"]["name"] == "t2"
