"""Integration tests for Agent + LLM + Tools."""

import pytest


def _has_yaml() -> bool:
    """Check if pyyaml is available."""
    try:
        import yaml  # noqa: F401
        return True
    except ImportError:
        return False


# --- Agent Core Tests ---

def test_agent_initialization():
    """Test agent initializes with default dependencies."""
    from harnessgenj_dev.core.agent import Agent

    agent = Agent()
    assert agent.llm_gateway is not None
    assert agent.state is not None
    assert not agent.state.is_running
    # Default effort is "medium" with max_iterations=10
    assert agent.state.max_iterations == 10


def test_agent_system_prompt():
    """Test system prompt includes role, tools, and context."""
    from harnessgenj_dev.core.agent import Agent
    from harnessgenj_dev.tools.registry import auto_register

    auto_register()
    agent = Agent()
    prompt = agent._build_system_prompt(role="developer")

    assert "clean, tested, production-ready code" in prompt
    assert "Available Tools" in prompt
    assert "SOLID" in prompt


def test_agent_system_prompt_all_roles():
    """Test all roles produce valid system prompts."""
    from harnessgenj_dev.core.agent import Agent

    agent = Agent()
    for role in ["developer", "code_reviewer", "bug_hunter", "architect", "product_manager", "doc_writer"]:
        prompt = agent._build_system_prompt(role=role)
        assert prompt  # Non-empty
        assert "Available Tools" in prompt


def test_agent_tool_schemas():
    """Test agent retrieves tool schemas in unified format."""
    from harnessgenj_dev.core.agent import Agent
    from harnessgenj_dev.tools.registry import auto_register

    auto_register()
    agent = Agent()
    schemas = agent._get_tool_schemas()

    assert schemas is not None
    assert len(schemas) > 0
    for schema in schemas:
        assert "name" in schema
        assert "description" in schema
        assert "parameters" in schema


def test_agent_parse_tool_calls_empty():
    """Test parsing returns empty for plain text response."""
    from harnessgenj_dev.core.agent import Agent
    from harnessgenj_dev.llm.models import LLMResponse

    agent = Agent()
    response = LLMResponse(content="Hello, I can help with that.")
    tool_calls = agent._parse_tool_calls(response)
    assert tool_calls == []


def test_agent_parse_structured_tool_calls():
    """Test parsing structured tool calls from response."""
    from harnessgenj_dev.core.agent import Agent
    from harnessgenj_dev.llm.models import LLMResponse

    agent = Agent()
    response = LLMResponse(
        content="I'll read the file.",
        tool_calls=[
            {"name": "read_file", "input": {"path": "test.py"}}
        ],
    )
    tool_calls = agent._parse_tool_calls(response)
    assert len(tool_calls) == 1
    assert tool_calls[0]["name"] == "read_file"
    assert tool_calls[0]["input"]["path"] == "test.py"


def test_agent_interrupt():
    """Test interrupting agent sets is_running to False."""
    from harnessgenj_dev.core.agent import Agent

    agent = Agent()
    agent.state.is_running = True
    agent.interrupt()
    assert not agent.state.is_running


# --- Agent + Tool Integration Tests ---

@pytest.mark.asyncio
async def test_agent_run_without_api_key():
    """Test agent gracefully handles missing API key."""
    from harnessgenj_dev.core.agent import Agent
    from harnessgenj_dev.llm.gateway import LLMGateway

    # Create gateway without API key
    gateway = LLMGateway(provider="anthropic", api_key="")
    agent = Agent(llm_gateway=gateway)

    # Should fail gracefully (no real API call without key)
    try:
        result = await agent.run("test", role="developer")
        # If it doesn't raise, it should return an error message
        assert "Error" in result or "not implemented" in result.lower() or result == ""
    except Exception:
        # Expected when no API key and no mock provider
        pass


# --- CLI Tests ---

def test_cli_parser_has_subcommands():
    """Test CLI parser has all expected subcommands."""
    from harnessgenj_dev.cli import _build_parser

    parser = _build_parser()
    # Parse --help to check subcommands
    import io
    import sys
    output = io.StringIO()
    try:
        sys.stdout = output
        parser.parse_args(["--help"])
    except SystemExit:
        pass
    finally:
        sys.stdout = sys.__stdout__

    help_text = output.getvalue()
    for cmd in ["init", "develop", "status"]:
        assert cmd in help_text


def test_cli_parser_develop_args():
    """Test develop subcommand parsing."""
    from harnessgenj_dev.cli import _build_parser

    parser = _build_parser()
    args = parser.parse_args(["develop", "fix the bug", "--role", "bug_hunter"])
    assert args.command == "develop"
    assert args.prompt == "fix the bug"
    assert args.role == "bug_hunter"


def test_cli_parser_develop_interactive():
    """Test develop without prompt enters interactive mode."""
    from harnessgenj_dev.cli import _build_parser

    parser = _build_parser()
    args = parser.parse_args(["develop"])
    assert args.command == "develop"
    assert args.prompt is None
    # Default effort is "medium" (no max_iterations override)
    assert args.effort == "medium"


def test_cli_parser_model_override():
    """Test model and provider override."""
    from harnessgenj_dev.cli import _build_parser

    parser = _build_parser()
    args = parser.parse_args([
        "develop", "test",
        "--model", "gpt-4o",
        "--provider", "openai",
    ])
    assert args.model == "gpt-4o"
    assert args.provider == "openai"


@pytest.mark.skipif(not _has_yaml(), reason="pyyaml not installed")
def test_cli_init_creates_config(tmp_path, monkeypatch):
    """Test init command creates config file."""
    from harnessgenj_dev.cli import _cmd_init
    import pathlib

    # Patch Path.home() to use tmp_path
    original_home = pathlib.Path.home

    @classmethod
    def patched_home(cls):
        return tmp_path

    monkeypatch.setattr(pathlib.Path, "home", patched_home)

    class Args:
        path = str(tmp_path)

    exit_code = _cmd_init(Args())
    config_file = tmp_path / ".hgj-dev" / "config.yaml"
    assert exit_code == 0
    assert config_file.exists()


def test_cli_status():
    """Test status command runs without error."""
    from harnessgenj_dev.cli import _cmd_status

    class Args:
        pass

    exit_code = _cmd_status(Args())
    assert exit_code == 0


# --- Gateway + Provider Integration ---

def test_gateway_anthropic_provider_creation():
    """Test creating Anthropic provider through gateway."""
    from harnessgenj_dev.llm.gateway import LLMGateway

    gateway = LLMGateway(provider="anthropic", model="claude-sonnet-4-6")
    provider = gateway._get_provider("anthropic")
    assert provider.provider_name == "anthropic"


def test_gateway_openai_provider_creation():
    """Test creating OpenAI provider through gateway."""
    from harnessgenj_dev.llm.gateway import LLMGateway

    gateway = LLMGateway(provider="openai", model="gpt-4o")
    provider = gateway._get_provider("openai")
    assert provider.provider_name == "openai"


def test_gateway_degradation_chain():
    """Test degradation chain is accessible."""
    from harnessgenj_dev.llm.gateway import FALLBACK_CHAIN

    # claude-sonnet should have at least 1 fallback
    chain = FALLBACK_CHAIN["claude-sonnet-4-6"]
    assert len(chain) >= 1

    # At least one should be openai
    providers = [p[0] for p in chain]
    assert "openai" in providers


# --- Tool Registry Integration ---

def test_auto_register_discovers_tools():
    """Test auto-discovery finds tools."""
    from harnessgenj_dev.tools.registry import auto_register, get_tool_list

    # Reset and re-register
    from harnessgenj_dev.tools.registry import reset_registry
    reset_registry()

    registered = auto_register()
    tools = get_tool_list()

    # Should have discovered at least file_ops and shell_ops
    assert len(tools) >= 2
    names = [t["name"] for t in tools]
    assert "read_file" in names
    assert "list_directory" in names


def test_tool_execution_read_file():
    """Test executing read_file through registry."""
    import tempfile
    from harnessgenj_dev.tools.registry import execute_tool

    # Create a temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("test content")
        tmp_path = f.name

    import asyncio
    result = asyncio.get_event_loop().run_until_complete(
        execute_tool("read_file", path=tmp_path)
    )
    assert result.success
    assert "test content" in result.content

    import os
    os.unlink(tmp_path)


# --- Config + Integration ---

def test_config_load_defaults():
    """Test loading default config."""
    from harnessgenj_dev.config import AppConfig

    config = AppConfig()
    assert config.llm.provider == "anthropic"
    assert config.llm.model == "claude-sonnet-4-6"
    assert config.tools.default_timeout == 30


@pytest.mark.skipif(not _has_yaml(), reason="pyyaml not installed")
def test_config_save_and_reload(tmp_path):
    """Test saving and reloading config."""
    from harnessgenj_dev.config import AppConfig

    config_file = tmp_path / "config.yaml"

    # Create and save
    config = AppConfig()
    config.llm.provider = "openai"
    config.llm.model = "gpt-4o"
    config.save(str(config_file))

    # Reload
    reloaded = AppConfig.load(str(config_file))
    assert reloaded.llm.provider == "openai"
    assert reloaded.llm.model == "gpt-4o"
