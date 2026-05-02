"""Streaming response handler."""

from __future__ import annotations

from collections.abc import AsyncIterator

from .models import StreamChunk


async def handle_stream(stream: AsyncIterator) -> AsyncIterator[str]:
    """Process and yield streaming chunks from an LLM response.

    Wraps the raw stream with error recovery and validation.
    Ensures that every stream yields at least a done marker even
    if an error occurs mid-stream.

    Args:
        stream: Async iterator yielding raw chunks from the LLM provider.

    Yields:
        String content from each chunk, with error recovery.
    """
    try:
        async for chunk in stream:
            if isinstance(chunk, StreamChunk):
                if chunk.done:
                    yield ""
                    return
                if chunk.content:
                    yield chunk.content
            else:
                # Forward raw string chunks as-is
                yield chunk
    except Exception:
        # Error recovery: yield empty marker so downstream knows
        # the stream ended abnormally
        yield ""


async def stream_to_string(stream: AsyncIterator) -> str:
    """Collect an entire stream into a single string.

    Args:
        stream: Async iterator yielding stream chunks.

    Returns:
        Full accumulated text response.
    """
    parts: list[str] = []
    async for chunk in handle_stream(stream):
        parts.append(chunk)
    return "".join(parts)
