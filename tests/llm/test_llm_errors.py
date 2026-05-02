"""Tests for LLM error handling."""
import pytest
from harnessgenj_dev.llm.gateway import LLMGateway


class TestLLMErrorHandling:
    """Test LLM error handling and degradation."""

    def test_invalid_provider_raises(self):
        gw = LLMGateway(provider="nonexistent")
        with pytest.raises(ValueError):
            gw._get_provider("nonexistent")

    def test_fallback_chain_exists(self):
        from harnessgenj_dev.llm.gateway import FALLBACK_CHAIN
        assert "claude-sonnet-4-6" in FALLBACK_CHAIN
        assert "claude-opus-4-6" in FALLBACK_CHAIN

    def test_degradation_with_empty_chain(self):
        gw = LLMGateway()
        with pytest.raises(Exception):
            import asyncio
            asyncio.get_event_loop().run_until_complete(
                gw._degrade([], None, "unknown-model", 0.1, 100, Exception("fail"))
            )
