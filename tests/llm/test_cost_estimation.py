"""Tests for cost estimation in LLM gateway."""
from harnessgenj_dev.llm.gateway import LLMGateway


class TestCostEstimation:
    """Test cost estimation functionality."""

    def test_estimate_anthropic(self):
        gw = LLMGateway(provider="anthropic", model="claude-sonnet-4-6")
        cost = gw.estimate_cost(1000, 500)
        assert cost > 0

    def test_estimate_openai(self):
        gw = LLMGateway(provider="openai", model="gpt-4o")
        cost = gw.estimate_cost(1000, 500)
        assert cost > 0

    def test_estimate_scales_with_tokens(self):
        gw = LLMGateway(provider="anthropic", model="claude-sonnet-4-6")
        cost1 = gw.estimate_cost(1000, 500)
        cost2 = gw.estimate_cost(2000, 1000)
        assert cost2 > cost1

    def test_estimate_zero_tokens(self):
        gw = LLMGateway(provider="anthropic", model="claude-sonnet-4-6")
        cost = gw.estimate_cost(0, 0)
        assert cost == 0
