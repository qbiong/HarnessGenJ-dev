"""Tests for LLM module."""


def test_gateway_init():
    """Test LLM gateway initialization."""
    from harnessgenj_dev.llm.gateway import LLMGateway

    gw = LLMGateway(provider="anthropic", model="claude-sonnet-4-6")
    assert gw.provider == "anthropic"
    assert gw.model == "claude-sonnet-4-6"


def test_token_counter():
    """Test token counting."""
    from harnessgenj_dev.llm.token_counter import count_tokens

    count = count_tokens("Hello, World!")
    assert count > 0


def test_model_router():
    """Test model selection."""
    from harnessgenj_dev.llm.model_router import select_model

    model = select_model(task="coding")
    assert model is not None
    assert model.name
