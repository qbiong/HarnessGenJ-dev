"""End-to-end tests for streaming responses with real API calls."""

import os

import pytest

from harnessgenj_dev.llm.gateway import LLMGateway
from harnessgenj_dev.llm.models import StreamChunk

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.anthropic,
    pytest.mark.slow,
    pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY", "").strip(),
        reason="ANTHROPIC_API_KEY not set",
    ),
]


class TestStreamingE2E:
    """Test streaming with real LLM API."""

    @pytest.mark.asyncio
    async def test_stream_yields_content(self):
        """Streaming response should yield content chunks."""
        gateway = LLMGateway(
            provider="anthropic",
            api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        )
        chunks = []
        async for chunk in gateway.stream(
            messages=[{"role": "user", "content": "Count from 1 to 3."}]
        ):
            chunks.append(chunk)

        assert len(chunks) > 0
        # At least some chunks should have content
        content_chunks = [c for c in chunks if c.content]
        assert len(content_chunks) > 0

    @pytest.mark.asyncio
    async def test_stream_final_done_chunk(self):
        """Streaming response should end with done=True."""
        gateway = LLMGateway(
            provider="anthropic",
            api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        )
        chunks = []
        async for chunk in gateway.stream(
            messages=[{"role": "user", "content": "Say hello."}]
        ):
            chunks.append(chunk)
            if chunk.done:
                break

        # Last chunk should have done=True
        assert chunks[-1].done is True

    @pytest.mark.asyncio
    async def test_stream_accumulated_content(self):
        """Accumulated stream content should be non-empty."""
        gateway = LLMGateway(
            provider="anthropic",
            api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        )
        content = ""
        async for chunk in gateway.stream(
            messages=[{"role": "user", "content": "What is the capital of France?"}]
        ):
            if chunk.content:
                content += chunk.content
            if chunk.done:
                break

        assert "paris" in content.lower()

    @pytest.mark.asyncio
    async def test_stream_usage_tracking(self):
        """Streaming response should report usage stats."""
        gateway = LLMGateway(
            provider="anthropic",
            api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        )
        last_usage = None
        async for chunk in gateway.stream(
            messages=[{"role": "user", "content": "Hi."}]
        ):
            if chunk.usage:
                last_usage = chunk.usage
            if chunk.done:
                break

        # Usage should be reported at some point
        assert last_usage is not None
        assert last_usage.input_tokens > 0
        assert last_usage.output_tokens > 0

    @pytest.mark.asyncio
    async def test_stream_longer_response(self):
        """Longer streaming response should yield multiple chunks."""
        gateway = LLMGateway(
            provider="anthropic",
            api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        )
        chunks = []
        async for chunk in gateway.stream(
            messages=[{
                "role": "user",
                "content": "Explain the concept of recursion in programming in 3 paragraphs."
            }]
        ):
            chunks.append(chunk)
            if chunk.done:
                break

        # Longer response should yield multiple chunks
        assert len(chunks) >= 2
        # Full content should be substantial
        total_content = "".join(c.content or "" for c in chunks)
        assert len(total_content) > 50
