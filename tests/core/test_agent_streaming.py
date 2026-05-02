"""Tests for agent streaming."""

import pytest

from harnessgenj_dev.core.agent import Agent


class TestAgentStreaming:
    """Test agent streaming behavior."""

    def test_agent_has_run_stream(self):
        """Agent should have run_stream method."""
        agent = Agent()
        assert hasattr(agent, "run_stream")

    @pytest.mark.asyncio
    async def test_stream_returns_iterable(self):
        """Stream should return an async iterator."""
        agent = Agent()
        result = agent.run_stream("test")
        assert result is not None
        # It's an async generator, should be iterable
        assert hasattr(result, "__aiter__")
