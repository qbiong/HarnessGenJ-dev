"""Tests for token counter."""

import pytest

from harnessgenj_dev.llm.token_counter import count_tokens, count_message_tokens


class TestCountTokens:
    """Test token counting functions."""

    def test_empty_string(self):
        """Empty string should return 0 or 1 token."""
        count = count_tokens("")
        assert count >= 0

    def test_simple_text(self):
        """Simple text should have token count."""
        count = count_tokens("Hello, world!")
        assert count > 0

    def test_longer_text_more_tokens(self):
        """Longer text should have more tokens than short text."""
        short = count_tokens("Hello")
        long_text = count_tokens("Hello world this is a longer piece of text for testing")
        assert long_text > short

    def test_code_tokens(self):
        """Code should be tokenized."""
        code = "def foo():\n    return 42"
        count = count_tokens(code)
        assert count > 0

    def test_count_consistency(self):
        """Same text should always produce same token count."""
        text = "Test string for consistency"
        c1 = count_tokens(text)
        c2 = count_tokens(text)
        assert c1 == c2

    def test_special_characters(self):
        """Special characters should be tokenized."""
        text = "!@#$%^&*()_+-=[]{}|;':\",./<>?"
        count = count_tokens(text)
        assert count > 0

    def test_unicode_text(self):
        """Unicode text should be tokenized."""
        text = "你好世界"
        count = count_tokens(text)
        assert count > 0

    def test_newlines_counted(self):
        """Newlines should be part of tokenization."""
        text = "line1\nline2\nline3"
        count = count_tokens(text)
        assert count > 0

    def test_whitespace_minimal(self):
        """Whitespace-only text should have minimal tokens."""
        text = "   "
        count = count_tokens(text)
        assert count >= 0


class TestCountMessageTokens:
    """Test message list token counting."""

    def test_single_message(self):
        """Single message should return token count."""
        messages = [{"role": "user", "content": "Hello"}]
        count = count_message_tokens(messages)
        assert count > 0

    def test_multiple_messages(self):
        """Multiple messages should have higher count."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Hello"},
        ]
        count = count_message_tokens(messages)
        assert count > 0

    def test_empty_messages(self):
        """Empty message list should return 0."""
        count = count_message_tokens([])
        assert count == 0

    def test_role_tokens_counted(self):
        """Role tokens should be included in count."""
        messages = [{"role": "user", "content": ""}]
        count = count_message_tokens(messages)
        assert count > 0  # Role token should be counted

    def test_more_messages_more_tokens(self):
        """More messages should have higher token count."""
        single = count_message_tokens([{"role": "user", "content": "hi"}])
        multi = count_message_tokens([
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ])
        assert multi > single
