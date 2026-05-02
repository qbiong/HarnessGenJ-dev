"""End-to-end tests for OpenAI provider with real API calls."""

import os

import pytest

from harnessgenj_dev.llm.gateway import LLMGateway
from harnessgenj_dev.llm.models import LLMResponse

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.openai,
    pytest.mark.slow,
    pytest.mark.skipif(
        not os.environ.get("OPENAI_API_KEY", "").strip(),
        reason="OPENAI_API_KEY not set",
    ),
]


class TestOpenAIChat:
    """Test OpenAI provider chat with real API."""

    @pytest.mark.asyncio
    async def test_simple_chat(self):
        """Basic chat should return a non-empty response."""
        gateway = LLMGateway(
            provider="openai",
            api_key=os.environ.get("OPENAI_API_KEY", ""),
        )
        response = await gateway.chat(
            messages=[{"role": "user", "content": "Say hello in one word."}]
        )
        assert isinstance(response, LLMResponse)
        assert len(response.content.strip()) > 0
        assert response.model != ""

    @pytest.mark.asyncio
    async def test_chat_with_system_prompt(self):
        """System prompt should influence the response."""
        gateway = LLMGateway(
            provider="openai",
            api_key=os.environ.get("OPENAI_API_KEY", ""),
        )
        response = await gateway.chat(
            messages=[
                {"role": "system", "content": "You are a pirate. Answer like one."},
                {"role": "user", "content": "How are you?"},
            ]
        )
        assert isinstance(response, LLMResponse)
        assert len(response.content.strip()) > 0
        # Should contain pirate-like language
        lower = response.content.lower()
        assert any(word in lower for word in ["ahoy", "matey", "arrr", "pirate", "ship", "sea", "yarr", "aye", "captain", "crew"])

    @pytest.mark.asyncio
    async def test_chat_multi_turn(self):
        """Multi-turn conversation should maintain context."""
        gateway = LLMGateway(
            provider="openai",
            api_key=os.environ.get("OPENAI_API_KEY", ""),
        )
        messages = [
            {"role": "user", "content": "My favorite color is blue."},
        ]
        # First turn
        response1 = await gateway.chat(messages=messages)
        messages.append({"role": "assistant", "content": response1.content})
        # Second turn — should remember the color
        messages.append({"role": "user", "content": "What is my favorite color?"})
        response2 = await gateway.chat(messages=messages)
        assert "blue" in response2.content.lower()

    @pytest.mark.asyncio
    async def test_chat_usage_stats(self):
        """Response should have token usage > 0."""
        gateway = LLMGateway(
            provider="openai",
            api_key=os.environ.get("OPENAI_API_KEY", ""),
        )
        response = await gateway.chat(
            messages=[{"role": "user", "content": "Say hi."}]
        )
        assert response.usage.input_tokens > 0
        assert response.usage.output_tokens > 0
        assert response.usage.total_tokens > 0

    @pytest.mark.asyncio
    async def test_chat_cost_estimation(self):
        """Cost estimation should be > 0 for a real response."""
        gateway = LLMGateway(
            provider="openai",
            model="gpt-4o",
            api_key=os.environ.get("OPENAI_API_KEY", ""),
        )
        response = await gateway.chat(
            messages=[{"role": "user", "content": "Say hi."}]
        )
        cost = gateway.estimate_cost(
            response.usage.input_tokens, response.usage.output_tokens
        )
        assert cost > 0

    @pytest.mark.asyncio
    async def test_chat_max_tokens(self):
        """max_tokens parameter should limit output length."""
        gateway = LLMGateway(
            provider="openai",
            api_key=os.environ.get("OPENAI_API_KEY", ""),
        )
        response = await gateway.chat(
            messages=[{"role": "user", "content": "Write a short poem about dogs."}],
            max_tokens=50,
        )
        assert response.content is not None
        assert response.usage.output_tokens <= 50

    @pytest.mark.asyncio
    async def test_chat_temperature(self):
        """Temperature parameter should not cause errors."""
        gateway = LLMGateway(
            provider="openai",
            api_key=os.environ.get("OPENAI_API_KEY", ""),
        )
        response = await gateway.chat(
            messages=[{"role": "user", "content": "What is 2+2?"}],
            temperature=0.0,
        )
        assert "4" in response.content
