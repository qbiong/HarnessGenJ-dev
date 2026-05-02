"""End-to-end tests for tool call parsing with real LLM responses."""

import os
import tempfile
from pathlib import Path

import pytest

from harnessgenj_dev.core.agent import Agent
from harnessgenj_dev.llm.gateway import LLMGateway
from harnessgenj_dev.tools.registry import auto_register, reset_registry

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.anthropic,
    pytest.mark.slow,
    pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY", "").strip(),
        reason="ANTHROPIC_API_KEY not set",
    ),
]


@pytest.fixture(autouse=True)
def _setup_tools():
    """Ensure tools are auto-registered before each test."""
    reset_registry()
    auto_register()
    yield
    reset_registry()


class TestToolCallsE2E:
    """Test tool call extraction and execution with real LLM."""

    @pytest.mark.asyncio
    async def test_no_tool_call_when_not_needed(self, tmp_path):
        """Simple questions should not trigger tool calls."""
        (tmp_path / "test.txt").write_text("Hello world")

        gateway = LLMGateway(
            provider="anthropic",
            api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        )
        agent = Agent(llm_gateway=gateway)

        # This simple question should be answerable without tools
        result = await agent.run("What is 2 + 2?")
        assert "4" in result
        # Should complete in 1 iteration (no tool calls needed)
        assert agent.state.iteration_count == 1

    @pytest.mark.asyncio
    async def test_tool_call_read_file(self, tmp_path):
        """Agent should use read_file tool when asked about file contents."""
        test_file = tmp_path / "sample.txt"
        test_file.write_text("The secret code is BANANA42")

        gateway = LLMGateway(
            provider="anthropic",
            api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        )
        agent = Agent(llm_gateway=gateway, tool_registry=None)

        # Ask agent to read a specific file
        result = await agent.run(
            f"Read the contents of the file at {test_file} and tell me the secret code."
        )
        # Agent should have read the file and found the code
        assert "BANANA42" in result

    @pytest.mark.asyncio
    async def test_tool_call_write_file(self, tmp_path):
        """Agent should use write_file tool when asked to create a file."""
        target_file = tmp_path / "output.txt"

        gateway = LLMGateway(
            provider="anthropic",
            api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        )
        agent = Agent(llm_gateway=gateway, tool_registry=None)

        # Ask agent to write a file
        await agent.run(
            f"Write exactly the text 'Hello from AI' to the file {target_file}"
        )

        # Verify file was created
        assert target_file.exists()
        content = target_file.read_text()
        assert "Hello from AI" in content

    @pytest.mark.asyncio
    async def test_tool_call_read_then_edit(self, tmp_path):
        """Agent should read before editing a file."""
        test_file = tmp_path / "editable.txt"
        test_file.write_text("The sky is blue.")

        gateway = LLMGateway(
            provider="anthropic",
            api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        )
        agent = Agent(llm_gateway=gateway, tool_registry=None)

        # Ask agent to change the color in the file
        await agent.run(
            f"Change the color in the file {test_file} from blue to red."
        )

        # Verify file was modified
        content = test_file.read_text()
        assert "red" in content.lower()

    @pytest.mark.asyncio
    async def test_tool_call_list_directory(self, tmp_path):
        """Agent should use list_directory tool when asked about files."""
        (tmp_path / "alpha.txt").write_text("a")
        (tmp_path / "beta.txt").write_text("b")

        gateway = LLMGateway(
            provider="anthropic",
            api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        )
        agent = Agent(llm_gateway=gateway, tool_registry=None)

        result = await agent.run(
            f"List all files in the directory {tmp_path} and tell me how many .txt files there are."
        )
        # Should mention at least 2 txt files
        assert "2" in result or "two" in result.lower()
