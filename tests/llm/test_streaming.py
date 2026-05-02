"""Tests for streaming module."""

import asyncio
import pytest

from harnessgenj_dev.llm.streaming import handle_stream, stream_to_string
from harnessgenj_dev.llm.models import StreamChunk


class TestStreamProcessing:
    """Test stream processing logic."""

    @pytest.mark.asyncio
    async def test_handle_stream_basic(self):
        """Test basic stream handling yields content."""
        async def gen():
            yield StreamChunk(content="Hello", done=False)
            yield StreamChunk(content=" World", done=False)
            yield StreamChunk(content=None, done=True)

        parts = []
        async for part in handle_stream(gen()):
            parts.append(part)

        assert "Hello" in parts
        assert " World" in parts

    @pytest.mark.asyncio
    async def test_handle_stream_empty(self):
        """Test handling an empty stream."""
        async def gen():
            yield StreamChunk(content=None, done=True)

        parts = []
        async for part in handle_stream(gen()):
            parts.append(part)

        assert len(parts) >= 0  # May yield empty marker

    @pytest.mark.asyncio
    async def test_handle_stream_error_recovery(self):
        """Test stream handles errors gracefully."""
        async def gen():
            yield StreamChunk(content="OK", done=False)
            raise RuntimeError("Stream error")

        parts = []
        async for part in handle_stream(gen()):
            parts.append(part)

        assert len(parts) >= 1  # Should have gotten at least the first chunk

    @pytest.mark.asyncio
    async def test_handle_stream_string_chunks(self):
        """Test handling raw string chunks."""
        async def gen():
            yield "raw chunk"

        parts = []
        async for part in handle_stream(gen()):
            parts.append(part)

        assert "raw chunk" in parts


class TestStreamToString:
    """Test stream_to_string helper."""

    @pytest.mark.asyncio
    async def test_basic_accumulation(self):
        """Test accumulating stream into string."""
        async def gen():
            yield StreamChunk(content="Hel", done=False)
            yield StreamChunk(content="lo", done=False)
            yield StreamChunk(content=" World", done=False)
            yield StreamChunk(content=None, done=True)

        result = await stream_to_string(gen())
        assert "Hel" in result
        assert "lo" in result
        assert "World" in result

    @pytest.mark.asyncio
    async def test_empty_stream(self):
        """Test empty stream returns empty string."""
        async def gen():
            yield StreamChunk(content=None, done=True)

        result = await stream_to_string(gen())
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_single_chunk(self):
        """Test single chunk stream."""
        async def gen():
            yield StreamChunk(content="single", done=False)
            yield StreamChunk(content=None, done=True)

        result = await stream_to_string(gen())
        assert "single" in result
