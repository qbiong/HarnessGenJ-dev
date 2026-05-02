"""Shared fixtures for end-to-end tests."""

import os

import pytest

from harnessgenj_dev.llm.gateway import LLMGateway
from harnessgenj_dev.tools.registry import auto_register, reset_registry


@pytest.fixture(autouse=True, scope="session")
def _e2e_register_tools():
    """Auto-register tools once per session for E2E tests."""
    auto_register()
    yield


@pytest.fixture
def anthropic_gateway():
    """Create LLMGateway configured for Anthropic with real API key."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    return LLMGateway(provider="anthropic", api_key=api_key)


@pytest.fixture
def openai_gateway():
    """Create LLMGateway configured for OpenAI with real API key."""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    return LLMGateway(provider="openai", api_key=api_key)


@pytest.fixture
def tool_registry():
    """Provide access to the tool registry's execute function.

    Returns a thin wrapper object with an execute() method that calls
    the module-level execute_tool function, matching what Agent expects.
    """
    from harnessgenj_dev.tools.registry import execute_tool

    class ToolRegistryWrapper:
        async def execute(self, name, **kwargs):
            return await execute_tool(name, **kwargs)

    return ToolRegistryWrapper()


@pytest.fixture
def has_anthropic_key() -> bool:
    """Whether ANTHROPIC_API_KEY is set."""
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


@pytest.fixture
def has_openai_key() -> bool:
    """Whether OPENAI_API_KEY is set."""
    return bool(os.environ.get("OPENAI_API_KEY", "").strip())
