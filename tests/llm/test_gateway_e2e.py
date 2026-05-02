"""Tests for LLM Gateway end-to-end with mocked providers."""

import pytest

from harnessgenj_dev.llm.gateway import LLMGateway
from harnessgenj_dev.llm.models import LLMResponse, StreamChunk, UsageReport
from harnessgenj_dev.llm.providers import BaseProvider


class MockProvider(BaseProvider):
    """Mock provider that returns predefined responses."""

    def __init__(self, name: str = "mock") -> None:
        self._name = name
        self.responses: list[LLMResponse] = []
        self.stream_items: list[StreamChunk] = []
        self.call_count: int = 0

    def set_responses(self, responses: list[LLMResponse]) -> None:
        self.responses = responses

    async def chat(self, messages, tools=None, model=None, stream=False, temperature=None, max_tokens=None, max_thinking_tokens=None):
        self.call_count += 1
        if self.call_count <= len(self.responses):
            return self.responses[self.call_count - 1]
        return LLMResponse(content="default mock response", model=self._name)

    async def stream(self, messages, tools=None, model=None, temperature=None, max_tokens=None, max_thinking_tokens=None):
        self.call_count += 1
        for item in self.stream_items:
            yield item
        yield StreamChunk(content="", done=True)

    @property
    def provider_name(self) -> str:
        return self._name

    def get_client(self):
        return None


class TestGatewayChat:
    """Test LLMGateway.chat() end-to-end."""

    @pytest.mark.asyncio
    async def test_chat_with_mocked_provider(self):
        gateway = LLMGateway(provider="mock-test", model="mock-model")
        provider = MockProvider("mock-test")
        provider.set_responses([
            LLMResponse(content="Hello from mock", model="mock-model")
        ])
        gateway.register_provider("mock-test", provider)

        result = await gateway.chat(
            messages=[{"role": "user", "content": "Hi"}]
        )
        assert result.content == "Hello from mock"

    @pytest.mark.asyncio
    async def test_chat_with_tools(self):
        gateway = LLMGateway(provider="mock-test", model="mock-model")
        provider = MockProvider("mock-test")
        tools = [{"type": "function", "function": {"name": "read_file"}}]
        provider.set_responses([
            LLMResponse(content="Using tools", model="m")
        ])
        gateway.register_provider("mock-test", provider)

        result = await gateway.chat(
            messages=[{"role": "user", "content": "Read file"}],
            tools=tools,
        )
        assert provider.call_count == 1
        assert result.content == "Using tools"

    @pytest.mark.asyncio
    async def test_chat_model_override(self):
        gateway = LLMGateway(provider="mock-test", model="mock-model")
        provider = MockProvider("mock-test")
        provider.set_responses([
            LLMResponse(content="overridden", model="custom-model")
        ])
        gateway.register_provider("mock-test", provider)

        result = await gateway.chat(
            messages=[{"role": "user", "content": "Hi"}],
            model="custom-model",
        )
        assert result.content == "overridden"


class TestGatewayStream:
    """Test LLMGateway.stream() with mocked provider."""

    @pytest.mark.asyncio
    async def test_stream_yields_chunks(self):
        gateway = LLMGateway(provider="mock-test", model="mock-model")
        provider = MockProvider("mock-test")
        provider.stream_items = [
            StreamChunk(content="Hello", done=False),
            StreamChunk(content=" world", done=False),
        ]
        gateway.register_provider("mock-test", provider)

        chunks = []
        async for chunk in gateway.stream(
            messages=[{"role": "user", "content": "Hi"}]
        ):
            chunks.append(chunk)
        # Gateway adds a final done=True chunk
        assert len(chunks) >= 3
        assert "".join(c.content for c in chunks if not c.done) == "Hello world"

    @pytest.mark.asyncio
    async def test_stream_usage_tracking(self):
        gateway = LLMGateway(provider="mock-test", model="mock-model")
        provider = MockProvider("mock-test")
        provider.stream_items = [
            StreamChunk(content="test", done=True, usage=UsageReport(
                input_tokens=10, output_tokens=5, total_tokens=15, estimated_cost=0.001
            )),
        ]
        gateway.register_provider("mock-test", provider)

        async for chunk in gateway.stream(
            messages=[{"role": "user", "content": "Hi"}]
        ):
            pass
        # Verify usage was recorded
        stats = gateway.get_usage_stats()
        assert stats.total_tokens == 15


class TestGatewayDegradation:
    """Test LLMGateway._degrade() fallback logic."""

    @pytest.mark.asyncio
    async def test_degrade_all_fallbacks_fail(self):
        """When primary fails and fallbacks also fail, error is raised."""
        gateway = LLMGateway(provider="mock-fail", model="claude-sonnet-4-6")
        provider = MockProvider("mock-fail")
        async def always_fail(messages, tools=None, model=None, stream=False, temperature=None, max_tokens=None, max_thinking_tokens=None):
            raise ConnectionError("All providers down")
        provider.chat = always_fail
        gateway.register_provider("mock-fail", provider)

        # Fallbacks try to create real OpenAI clients which fail without API key
        with pytest.raises(Exception):
            await gateway.chat(
                messages=[{"role": "user", "content": "Hi"}]
            )

    @pytest.mark.asyncio
    async def test_degrade_model_not_in_chain(self):
        """Model not in FALLBACK_CHAIN should raise original error immediately."""
        gateway = LLMGateway(provider="mock-fail", model="some-unknown-model-123")
        provider = MockProvider("mock-fail")
        async def always_fail(messages, tools=None, model=None, stream=False, temperature=None, max_tokens=None, max_thinking_tokens=None):
            raise ConnectionError("Primary down")
        provider.chat = always_fail
        gateway.register_provider("mock-fail", provider)

        with pytest.raises((ConnectionError, ValueError)):
            await gateway.chat(
                messages=[{"role": "user", "content": "Hi"}]
            )


class TestGatewayCostEstimation:
    """Test estimate_cost for various models."""

    def test_estimate_cost_anthropic_sonnet(self):
        gateway = LLMGateway(provider="anthropic", model="claude-sonnet-4-6")
        cost = gateway.estimate_cost(1000, 500)
        assert cost > 0

    def test_estimate_cost_anthropic_opus(self):
        gateway = LLMGateway(provider="anthropic", model="claude-opus-4-6")
        cost = gateway.estimate_cost(1000, 500)
        assert cost > 0

    def test_estimate_cost_anthropic_haiku(self):
        gateway = LLMGateway(provider="anthropic", model="claude-haiku-4-5-20251001")
        cost = gateway.estimate_cost(1000, 500)
        assert cost > 0

    def test_estimate_cost_gpt4o(self):
        gateway = LLMGateway(provider="openai", model="gpt-4o")
        cost = gateway.estimate_cost(1000, 500)
        assert cost > 0

    def test_estimate_cost_gpt4o_mini(self):
        gateway = LLMGateway(provider="openai", model="gpt-4o-mini")
        cost = gateway.estimate_cost(1000, 500)
        assert cost > 0

    def test_estimate_cost_zero_tokens(self):
        gateway = LLMGateway(provider="anthropic", model="claude-sonnet-4-6")
        cost = gateway.estimate_cost(0, 0)
        assert cost == 0.0


class TestGatewayUsageStats:
    """Test usage statistics tracking."""

    @pytest.mark.asyncio
    async def test_usage_tracks_multiple_calls(self):
        gateway = LLMGateway(provider="mock-test", model="mock-model")
        provider = MockProvider("mock-test")
        provider.set_responses([
            LLMResponse(content="Hi", model="m", usage=UsageReport(
                input_tokens=10, output_tokens=5, total_tokens=15, estimated_cost=0.001
            )),
            LLMResponse(content="Bye", model="m", usage=UsageReport(
                input_tokens=20, output_tokens=10, total_tokens=30, estimated_cost=0.002
            )),
        ])
        gateway.register_provider("mock-test", provider)

        await gateway.chat(messages=[{"role": "user", "content": "1"}])
        await gateway.chat(messages=[{"role": "user", "content": "2"}])

        stats = gateway.get_usage_stats()
        assert stats.input_tokens == 30
        assert stats.output_tokens == 15
