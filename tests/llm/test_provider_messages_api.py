"""Tests for Anthropic provider."""
import pytest
from harnessgenj_dev.llm.providers.messages_api import MessagesAPIProvider


class TestMessagesAPIProviderInit:
    """Test MessagesAPIProvider initialization."""

    def test_provider_name(self):
        p = MessagesAPIProvider()
        assert p.provider_name == "anthropic"

    def test_custom_api_key(self):
        p = MessagesAPIProvider(api_key="test-key")
        assert p.api_key == "test-key"

    def test_custom_base_url(self):
        p = MessagesAPIProvider(base_url="http://proxy:8080")
        assert p.base_url == "http://proxy:8080"

    def test_tool_conversion(self):
        p = MessagesAPIProvider()
        tools = [{"name": "test", "description": "A test tool", "parameters": {"type": "object"}}]
        result = p._convert_tool_format(tools)
        assert len(result) == 1
        assert result[0]["name"] == "test"
        assert "input_schema" in result[0]

    def test_tool_conversion_multiple(self):
        p = MessagesAPIProvider()
        tools = [
            {"name": "t1", "description": "Tool 1", "parameters": {"type": "object"}},
            {"name": "t2", "description": "Tool 2", "parameters": {"type": "object"}},
        ]
        result = p._convert_tool_format(tools)
        assert len(result) == 2
        assert result[0]["name"] == "t1"
        assert result[1]["name"] == "t2"

    def test_tool_conversion_empty_params(self):
        p = MessagesAPIProvider()
        tools = [{"name": "empty"}]
        result = p._convert_tool_format(tools)
        assert result[0]["input_schema"]["type"] == "object"
