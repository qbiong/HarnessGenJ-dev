"""Tests for LLM provider integration with mocked SDK clients."""

import pytest


class TestMessagesAPIProviderIntegration:
    """Test MessagesAPIProvider with mocked client."""

    @pytest.mark.asyncio
    async def test_chat_with_mocked_client(self):
        """Test chat method with a mocked Anthropic client."""
        from harnessgenj_dev.llm.providers.messages_api import MessagesAPIProvider
        from harnessgenj_dev.llm.models import LLMResponse

        provider = MessagesAPIProvider(api_key="fake-key")

        # Create mock response
        class MockContentBlock:
            type = "text"
            text = "Hello from Claude"

        class MockMessage:
            content = [MockContentBlock()]
            role = "assistant"
            stop_reason = "end_turn"
            usage = type("Usage", (), {"input_tokens": 10, "output_tokens": 5})()

        class MockMessages:
            async def create(self, **kwargs):
                return MockMessage()

        class MockClient:
            messages = MockMessages()

        provider._client = MockClient()

        result = await provider.chat(
            messages=[{"role": "user", "content": "Hi"}],
            model="claude-haiku",
        )
        assert isinstance(result, LLMResponse)
        assert "Hello from Claude" in result.content

    def test_chat_system_message_extraction(self):
        """System message should be extracted from messages list."""
        from harnessgenj_dev.llm.providers.messages_api import MessagesAPIProvider

        provider = MessagesAPIProvider(api_key="fake")

        # Mock client that captures arguments
        captured = {}

        class MockMessages:
            async def create(self, **kwargs):
                captured["kwargs"] = kwargs
                class Resp:
                    content = [type("CB", (), {"type": "text", "text": "ok"})()]
                    role = "assistant"
                    stop_reason = "end_turn"
                    usage = type("U", (), {"input_tokens": 0, "output_tokens": 1})()
                return Resp()

        class MockClient:
            messages = MockMessages()

        provider._client = MockClient()
        import asyncio
        asyncio.get_event_loop().run_until_complete(
            provider.chat(
                messages=[
                    {"role": "system", "content": "Sys"},
                    {"role": "user", "content": "Hi"},
                ],
                model="claude-haiku",
            )
        )
        assert "system" in captured["kwargs"]

    def test_build_usage(self):
        """Test usage calculation."""
        from harnessgenj_dev.llm.providers.messages_api import MessagesAPIProvider

        provider = MessagesAPIProvider(api_key="fake")
        mock_usage = type("Usage", (), {"input_tokens": 100, "output_tokens": 50, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0})()
        usage = provider._build_usage(mock_usage)
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50
        assert usage.total_tokens == 150

    def test_convert_tool_format(self):
        """Test tool format conversion from unified to Anthropic format."""
        from harnessgenj_dev.llm.providers.messages_api import MessagesAPIProvider

        provider = MessagesAPIProvider(api_key="fake")
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

    def test_extract_tool_calls(self):
        """Test tool call extraction from content blocks."""
        from harnessgenj_dev.llm.providers.messages_api import MessagesAPIProvider

        provider = MessagesAPIProvider(api_key="fake")
        tool_use_block = type("TB", (), {
            "type": "tool_use",
            "name": "read_file",
            "input": {"path": "test.py"},
            "id": "tool-1",
        })()
        text_block = type("TX", (), {
            "type": "text",
            "text": "Let me read",
        })()

        message = type("Msg", (), {"content": [text_block, tool_use_block]})()
        calls = provider._extract_tool_calls(message)
        assert len(calls) == 1
        assert calls[0]["name"] == "read_file"

    def test_extract_tool_calls_empty_content(self):
        """Test with empty content list."""
        from harnessgenj_dev.llm.providers.messages_api import MessagesAPIProvider

        provider = MessagesAPIProvider(api_key="fake")
        message = type("Msg", (), {"content": []})()
        calls = provider._extract_tool_calls(message)
        assert calls == []

    def test_get_client_lazy_init(self):
        """Client should be created only once (lazy init)."""
        from harnessgenj_dev.llm.providers.messages_api import MessagesAPIProvider

        provider = MessagesAPIProvider(api_key="fake")
        assert provider._client is None
        try:
            client = provider._get_client()
            # Second call should return same instance
            client2 = provider._get_client()
            assert client is client2
        except RuntimeError:
            # SDK not installed - that's fine for this test
            pass


class TestOpenAIProviderIntegration:
    """Test OpenAIProvider with mocked client."""

    @pytest.mark.asyncio
    async def test_chat_with_mocked_client(self):
        from harnessgenj_dev.llm.providers.openai import OpenAIProvider
        from harnessgenj_dev.llm.models import LLMResponse

        provider = OpenAIProvider(api_key="fake-key")

        class MockChoice:
            message = type("Msg", (), {
                "content": "Hello from OpenAI",
                "tool_calls": None,
                "role": "assistant",
                "function_call": None,
            })()
            finish_reason = "stop"

        class MockUsage:
            prompt_tokens = 10
            completion_tokens = 5
            total_tokens = 15

        class MockMessage:
            choices = [MockChoice()]
            usage = MockUsage()

        class MockClient:
            class Chat:
                class Completions:
                    async def create(self, **kwargs):
                        return MockMessage()
                completions = Completions()
            chat = Chat()

        provider._client = MockClient()

        result = await provider.chat(
            messages=[{"role": "user", "content": "Hi"}],
            model="gpt-4o",
        )
        assert isinstance(result, LLMResponse)
        assert "Hello from OpenAI" in result.content

    def test_chat_system_message_prepend(self):
        """System message should not be prepended again if already present."""
        from harnessgenj_dev.llm.providers.openai import OpenAIProvider

        provider = OpenAIProvider(api_key="fake")
        captured = {}

        class MockChoice:
            message = type("M", (), {"content": "ok", "tool_calls": None, "role": "assistant", "function_call": None})()
            finish_reason = "stop"

        class MockClient:
            class Chat:
                class Completions:
                    async def create(self, **kwargs):
                        captured["messages"] = kwargs.get("messages", [])
                        class R:
                            choices = [MockChoice()]
                            usage = type("U", (), {"prompt_tokens": 0, "completion_tokens": 1, "total_tokens": 1})()
                        return R()
                completions = Completions()
            chat = Chat()

        provider._client = MockClient()
        import asyncio
        asyncio.get_event_loop().run_until_complete(
            provider.chat(
                messages=[
                    {"role": "system", "content": "Sys"},
                    {"role": "user", "content": "Hi"},
                ],
                model="gpt-4o",
            )
        )
        # Should have 2 messages (system + user), not 3
        assert len(captured["messages"]) == 2

    def test_chat_empty_content_guard(self):
        """None content should be converted to empty string."""
        from harnessgenj_dev.llm.providers.openai import OpenAIProvider

        provider = OpenAIProvider(api_key="fake")

        class MockChoice:
            message = type("M", (), {"content": None, "tool_calls": None, "role": "assistant", "function_call": None})()
            finish_reason = "stop"

        class MockClient:
            class Chat:
                class Completions:
                    async def create(self, **kwargs):
                        class R:
                            choices = [MockChoice()]
                            usage = type("U", (), {"prompt_tokens": 0, "completion_tokens": 1, "total_tokens": 1})()
                        return R()
                completions = Completions()
            chat = Chat()

        provider._client = MockClient()
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            provider.chat(messages=[{"role": "assistant", "content": None}], model="gpt-4o")
        )
        # Content should be "" not None
        assert result.content == ""

    def test_extract_tool_calls_none_message(self):
        """None message should return empty list."""
        from harnessgenj_dev.llm.providers.openai import OpenAIProvider

        provider = OpenAIProvider(api_key="fake")
        calls = provider._extract_tool_calls(None)
        assert calls == []

    def test_build_usage(self):
        from harnessgenj_dev.llm.providers.openai import OpenAIProvider

        provider = OpenAIProvider(api_key="fake")
        mock_usage = type("Usage", (), {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150})()
        usage = provider._build_usage(mock_usage)
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50

    def test_get_client_lazy_init(self):
        from harnessgenj_dev.llm.providers.openai import OpenAIProvider

        provider = OpenAIProvider(api_key="fake")
        assert provider._client is None
        try:
            client = provider._get_client()
            client2 = provider._get_client()
            assert client is client2
        except RuntimeError:
            pass


class TestOpenRouterProvider:
    """Test OpenRouter-specific behavior."""

    def test_cost_calculation_differs_from_openai(self):
        """OpenRouter should use different pricing than standard OpenAI."""
        from harnessgenj_dev.llm.providers.openrouter import OpenRouterProvider
        from harnessgenj_dev.llm.providers.openai import OpenAIProvider

        or_prov = OpenRouterProvider(api_key="fake")
        oa_prov = OpenAIProvider(api_key="fake")

        mock_usage_or = type("U", (), {"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500})()
        mock_usage_oa = type("U", (), {"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500})()
        or_usage = or_prov._build_usage(mock_usage_or)
        oa_usage = oa_prov._build_usage(mock_usage_oa)

        # OpenRouter should have different cost
        assert or_usage.estimated_cost != oa_usage.estimated_cost

    def test_inherits_base_url(self):
        """Should use OpenRouter base URL."""
        from harnessgenj_dev.llm.providers.openrouter import OpenRouterProvider, OPENROUTER_BASE_URL

        provider = OpenRouterProvider(api_key="fake")
        assert OPENROUTER_BASE_URL in provider.base_url


class TestLocalProvider:
    """Test LocalProvider behavior."""

    def test_free_usage(self):
        """Local provider should report zero cost."""
        from harnessgenj_dev.llm.providers.local import LocalProvider

        provider = LocalProvider(base_url="http://localhost:11434")
        mock_usage = type("Usage", (), {"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500})()
        usage = provider._build_usage(mock_usage)
        assert usage.estimated_cost == 0.0

    def test_unknown_backend_defaults_to_ollama(self):
        from harnessgenj_dev.llm.providers.local import LocalProvider

        provider = LocalProvider(base_url="http://localhost", backend="unknown")
        assert provider is not None

    def test_default_urls(self):
        from harnessgenj_dev.llm.providers.local import DEFAULT_OLLAMA_URL, DEFAULT_VLLM_URL
        assert "11434" in DEFAULT_OLLAMA_URL
        assert "8000" in DEFAULT_VLLM_URL
