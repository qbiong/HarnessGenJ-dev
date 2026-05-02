"""Tests for context compression."""

from harnessgenj_dev.core.context_manager import ContextWindow


class TestContextCompression:
    """Test context compression behavior."""

    def test_compress_empty_context(self):
        """Compressing empty context returns empty."""
        cw = ContextWindow()
        compressed = cw.compress()
        assert len(compressed) == 0

    def test_compress_small_context(self):
        """Small context should not be compressed."""
        cw = ContextWindow()
        cw.add_message({"role": "user", "content": "Hello"}, token_count=1)
        compressed = cw.compress()
        assert len(compressed) >= 1

    def test_compress_large_context(self):
        """Large context should be reduced."""
        cw = ContextWindow()
        # System message
        cw.add_message({"role": "system", "content": "You are an assistant"}, token_count=5)
        # Many messages to trigger compression (needs > 12 messages for compression)
        for i in range(20):
            cw.add_message({"role": "user", "content": f"Message {i}"}, token_count=10)
        compressed = cw.compress()
        # Should keep system + recent 10 + summary
        assert len(compressed) < len(cw.messages)

    def test_compress_preserves_system(self):
        """System message should be preserved after compression."""
        cw = ContextWindow()
        cw.add_message({"role": "system", "content": "You are an assistant"}, token_count=5)
        for i in range(20):
            cw.add_message({"role": "user", "content": f"Message {i}"}, token_count=10)
        compressed = cw.compress()
        assert any(m.get("role") == "system" for m in compressed)
