"""Token counter and cost estimation using tiktoken."""

from __future__ import annotations

try:
    import tiktoken

    _HAS_TIKTOKEN = True
except ImportError:
    _HAS_TIKTOKEN = False


def _simple_token_count(text: str) -> int:
    """Simple fallback: approximate tokens as ~4 chars per token."""
    return max(1, len(text) // 4)


def count_tokens(text: str, model: str = "cl100k_base") -> int:
    """Count tokens in a text string."""
    if _HAS_TIKTOKEN:
        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    return _simple_token_count(text)


def count_message_tokens(messages: list[dict[str, str]], model: str = "cl100k_base") -> int:
    """Count tokens in a list of chat messages."""
    total = 0
    for msg in messages:
        total += count_tokens(msg.get("content", ""), model)
        total += count_tokens(msg.get("role", ""), model)
    # Base token overhead per message
    total += len(messages) * 3
    return total
