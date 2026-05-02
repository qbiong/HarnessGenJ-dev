"""Integration tests for end-to-end workflow."""
from harnessgenj_dev.llm.gateway import LLMGateway
from harnessgenj_dev.llm.models import LLMResponse, UsageReport


class TestEndToEndWorkflow:
    """Test complete workflow through the system."""

    def test_gateway_creation(self):
        gw = LLMGateway(provider="anthropic")
        assert gw.provider == "anthropic"

    def test_gateway_switch_provider(self):
        gw = LLMGateway()
        gw.set_provider("openai", "gpt-4o")
        assert gw.provider == "openai"
        assert gw.model == "gpt-4o"

    def test_usage_tracking_workflow(self):
        gw = LLMGateway()
        for i in range(5):
            gw._track_usage(UsageReport(
                input_tokens=100 * (i + 1),
                output_tokens=50 * (i + 1),
                total_tokens=150 * (i + 1),
                estimated_cost=0.001 * (i + 1),
            ))
        stats = gw.get_usage_stats()
        assert stats.input_tokens > 0
        assert stats.estimated_cost > 0
