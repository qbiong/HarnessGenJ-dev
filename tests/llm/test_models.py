"""Tests for LLM models dataclasses."""
from harnessgenj_dev.llm.models import LLMResponse, StreamChunk, UsageReport


class TestUsageReport:
    """Test UsageReport dataclass."""

    def test_default_values(self):
        report = UsageReport()
        assert report.input_tokens == 0
        assert report.output_tokens == 0
        assert report.total_tokens == 0
        assert report.estimated_cost == 0

    def test_custom_values(self):
        report = UsageReport(
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
            estimated_cost=0.05,
        )
        assert report.input_tokens == 1000
        assert report.output_tokens == 500
        assert report.total_tokens == 1500
        assert report.estimated_cost == 0.05

    def test_cache_tokens(self):
        report = UsageReport(
            cache_creation_tokens=200,
            cache_read_tokens=100,
        )
        assert report.cache_creation_tokens == 200
        assert report.cache_read_tokens == 100


class TestLLMResponse:
    """Test LLMResponse dataclass."""

    def test_text_response(self):
        resp = LLMResponse(content="Hello")
        assert resp.content == "Hello"
        assert resp.error is None
        assert resp.tool_calls == []  # Default is empty list, not None

    def test_error_response(self):
        resp = LLMResponse(content="", error="Something went wrong")
        assert resp.error == "Something went wrong"
        assert resp.content == ""

    def test_tool_call_response(self):
        tool_calls = [{"id": "1", "name": "test_tool", "input": {"arg": "val"}}]
        resp = LLMResponse(content="", tool_calls=tool_calls)
        assert resp.tool_calls == tool_calls
        assert len(resp.tool_calls) == 1

    def test_finish_reason_stop(self):
        resp = LLMResponse(content="done", finish_reason="stop")
        assert resp.finish_reason == "stop"

    def test_finish_reason_length(self):
        resp = LLMResponse(content="", finish_reason="length")
        assert resp.finish_reason == "length"

    def test_finish_reason_tool_calls(self):
        resp = LLMResponse(content="", finish_reason="tool_calls")
        assert resp.finish_reason == "tool_calls"


class TestStreamChunk:
    """Test StreamChunk dataclass."""

    def test_text_chunk(self):
        chunk = StreamChunk(content="Hello", done=False)
        assert chunk.content == "Hello"
        assert not chunk.done

    def test_done_chunk(self):
        chunk = StreamChunk(content=None, done=True)
        assert chunk.done
        assert chunk.content is None

    def test_chunk_with_usage(self):
        usage = UsageReport(input_tokens=10, output_tokens=5, total_tokens=15)
        chunk = StreamChunk(content=None, done=True, usage=usage)
        assert chunk.usage is not None
        assert chunk.usage.input_tokens == 10

    def test_chunk_with_error(self):
        chunk = StreamChunk(content=None, done=True, error="Stream failed")
        assert chunk.error == "Stream failed"
