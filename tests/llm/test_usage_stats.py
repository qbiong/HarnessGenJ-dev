"""Tests for usage statistics tracking."""
from harnessgenj_dev.llm.gateway import LLMGateway
from harnessgenj_dev.llm.models import UsageReport


class TestUsageStats:
    """Test usage statistics."""

    def test_initial_stats(self):
        gw = LLMGateway()
        stats = gw.get_usage_stats()
        assert stats.input_tokens == 0

    def test_accumulate_stats(self):
        gw = LLMGateway()
        gw._track_usage(UsageReport(input_tokens=100, output_tokens=50, total_tokens=150, estimated_cost=0.001))
        gw._track_usage(UsageReport(input_tokens=200, output_tokens=100, total_tokens=300, estimated_cost=0.003))
        stats = gw.get_usage_stats()
        assert stats.input_tokens == 300
        assert stats.output_tokens == 150

    def test_reset_stats(self):
        gw = LLMGateway()
        gw._track_usage(UsageReport(input_tokens=100, output_tokens=50, total_tokens=150))
        gw.reset_usage_stats()
        stats = gw.get_usage_stats()
        assert stats.input_tokens == 0
