"""Tests for core module."""


def test_agent_init():
    """Test agent initializes correctly."""
    from harnessgenj_dev.core.agent import Agent

    agent = Agent()
    assert agent.state is not None
    # Default effort is "medium" which sets max_iterations to 10
    assert agent.state.max_iterations == 10


def test_system_prompt_builder():
    """Test system prompt building."""
    from harnessgenj_dev.core.system_prompt import SystemPromptBuilder

    builder = SystemPromptBuilder()
    prompt = builder.with_role("developer").build()
    assert "Developer" in prompt


def test_context_manager():
    """Test context window management."""
    from harnessgenj_dev.core.context_manager import ContextWindow

    ctx = ContextWindow(max_tokens=1000)
    assert not ctx.needs_compression()
    ctx.total_tokens = 900
    assert ctx.needs_compression()
