"""Tests for Agent core methods with mocked LLM gateway."""

import json
import pytest

from harnessgenj_dev.core.agent import Agent, AgentState, ThoughtAction
from harnessgenj_dev.llm.models import LLMResponse


# ============================================================
# Mock LLM Gateway for testing
# ============================================================


class MockLLMGateway:
    """Mock LLM gateway that returns predefined responses."""

    def __init__(self) -> None:
        self.responses: list[LLMResponse] = []
        self.stream_chunks: list = []
        self.call_count: int = 0
        self.last_messages: list = []
        self.last_tools: list = []

    def set_responses(self, responses: list[LLMResponse]) -> None:
        """Queue responses for successive chat calls."""
        self.responses = responses

    async def chat(self, messages, tools=None, **kwargs):
        self.call_count += 1
        self.last_messages = messages
        self.last_tools = tools
        if self.call_count <= len(self.responses):
            return self.responses[self.call_count - 1]
        # Default: return empty content
        return LLMResponse(content="No more responses.", model="mock")

    async def stream(self, messages, tools=None, **kwargs):
        self.call_count += 1
        self.last_messages = messages
        for chunk in self.stream_chunks:
            yield chunk


class MockToolRegistry:
    """Mock tool registry for testing."""

    def __init__(self) -> None:
        self.results: dict[str, dict] = {}

    def set_result(self, name: str, success: bool = True, content: str = "ok", error: str = ""):
        self.results[name] = {"success": success, "content": content, "error": error}

    async def execute(self, name, **kwargs):
        result = self.results.get(name, {"success": True, "content": f"{name} done", "error": ""})
        from dataclasses import dataclass

        @dataclass
        class ToolResult:
            success: bool
            content: str
            error: str = ""

        return ToolResult(
            success=result["success"],
            content=result["content"],
            error=result.get("error", ""),
        )


# ============================================================
# Tests
# ============================================================


class TestAgentInit:
    """Test Agent initialization."""

    def test_create_with_defaults(self):
        agent = Agent()
        # Default effort is "medium" which sets max_iterations to 10
        assert agent.state.max_iterations == 10
        assert agent.state.iteration_count == 0
        assert agent.state.is_running is False
        assert agent.state.conversation_history == []

    def test_create_with_custom_tool_registry(self):
        reg = MockToolRegistry()
        agent = Agent(tool_registry=reg)
        assert agent.tool_registry is reg


class TestAgentRun:
    """Test Agent.run() method."""

    @pytest.mark.asyncio
    async def test_run_happy_path_no_tool_calls(self):
        """LLM returns content without tool calls on first call."""
        gateway = MockLLMGateway()
        gateway.set_responses([LLMResponse(content="Hello, I can help with that.")])
        reg = MockToolRegistry()
        agent = Agent(gateway, reg)

        result = await agent.run("Say hello")
        assert result == "Hello, I can help with that."
        assert gateway.call_count == 1
        assert agent.state.is_running is False  # Cleaned up

    @pytest.mark.asyncio
    async def test_run_max_iterations(self):
        """Agent should stop after max_iterations with tool calls each time."""
        gateway = MockLLMGateway()
        gateway.set_responses([
            LLMResponse(
                content="",
                tool_calls=[{"name": "read_file", "input": {"path": "test.py"}}],
            ),
            LLMResponse(
                content="",
                tool_calls=[{"name": "read_file", "input": {"path": "test.py"}}],
            ),
            LLMResponse(content="Max reached"),
        ])
        reg = MockToolRegistry()
        agent = Agent(gateway, reg)
        agent.state.max_iterations = 3

        result = await agent.run("loop forever")
        assert "Max reached" in result
        assert agent.state.iteration_count == 3

    @pytest.mark.asyncio
    async def test_run_llm_error(self):
        """Agent should return error string when LLM call fails."""
        gateway = MockLLMGateway()

        async def failing_chat(messages, tools=None, **kwargs):
            raise ConnectionError("Network down")

        gateway.chat = failing_chat
        reg = MockToolRegistry()
        agent = Agent(gateway, reg)

        result = await agent.run("test")
        assert "Error" in result
        assert "Network down" in result

    @pytest.mark.asyncio
    async def test_run_llm_response_error(self):
        """Agent should return error when response has error field."""
        gateway = MockLLMGateway()
        gateway.set_responses([
            LLMResponse(content="", error="Rate limited")
        ])
        reg = MockToolRegistry()
        agent = Agent(gateway, reg)

        result = await agent.run("test")
        assert "Error" in result
        assert "Rate limited" in result


class TestAgentReactLoop:
    """Test the _react_loop method directly."""

    @pytest.mark.asyncio
    async def test_react_loop_with_tool_execution(self):
        """Test tool call -> execution -> second LLM call -> final answer."""
        gateway = MockLLMGateway()
        gateway.set_responses([
            LLMResponse(
                content="Let me read the file",
                tool_calls=[{"name": "read_file", "input": {"path": "test.py"}}],
            ),
            LLMResponse(content="The file contains 'hello'."),
        ])
        reg = MockToolRegistry()
        reg.set_result("read_file", success=True, content="hello world")
        agent = Agent(gateway, reg)
        agent.state.conversation_history.append(
            {"role": "system", "content": "You are a test agent"}
        )
        agent.state.conversation_history.append(
            {"role": "user", "content": "Read test.py"}
        )

        result = await agent._react_loop()
        assert "hello" in result
        assert gateway.call_count == 2  # First call + after tool result

    @pytest.mark.asyncio
    async def test_react_loop_conversation_history_grows(self):
        """Verify conversation history grows across iterations."""
        gateway = MockLLMGateway()
        gateway.set_responses([
            LLMResponse(
                content="",
                tool_calls=[{"name": "read_file", "input": {"path": "a.py"}}],
            ),
            LLMResponse(
                content="",
                tool_calls=[{"name": "read_file", "input": {"path": "b.py"}}],
            ),
            LLMResponse(content="Done"),
        ])
        reg = MockToolRegistry()
        agent = Agent(gateway, reg)
        agent.state.conversation_history.append(
            {"role": "user", "content": "test"}
        )

        await agent._react_loop()
        # system not added in this direct test, but user + 2 assistants + 2 tool results
        assert len(agent.state.conversation_history) >= 5


class TestAgentExecuteToolCall:
    """Test _execute_tool_call method."""

    @pytest.mark.asyncio
    async def test_successful_tool_execution(self, monkeypatch):
        from dataclasses import dataclass

        @dataclass
        class MockResult:
            success: bool
            content: str
            error: str = ""

        async def mock_execute(name, **kwargs):
            return MockResult(success=True, content="file content")

        monkeypatch.setattr("harnessgenj_dev.core.agent.execute_tool", mock_execute)
        agent = Agent(MockLLMGateway())

        result = await agent._execute_tool_call(
            {"name": "read_file", "input": {"path": "test.py"}}
        )
        assert result["role"] == "tool"
        assert "[read_file]" in result["content"]
        assert "file content" in result["content"]

    @pytest.mark.asyncio
    async def test_tool_execution_failure(self, monkeypatch):
        from dataclasses import dataclass

        @dataclass
        class MockResult:
            success: bool
            content: str
            error: str = ""

        async def mock_execute(name, **kwargs):
            return MockResult(success=False, content="", error="File not found")

        monkeypatch.setattr("harnessgenj_dev.core.agent.execute_tool", mock_execute)
        agent = Agent(MockLLMGateway())

        result = await agent._execute_tool_call(
            {"name": "read_file", "input": {"path": "missing.py"}}
        )
        assert result["role"] == "tool"
        assert "Error" in result["content"]

    @pytest.mark.asyncio
    async def test_tool_execution_exception(self, monkeypatch):
        async def mock_execute(name, **kwargs):
            raise RuntimeError("Internal error")

        monkeypatch.setattr("harnessgenj_dev.core.agent.execute_tool", mock_execute)
        agent = Agent(MockLLMGateway())
        result = await agent._execute_tool_call(
            {"name": "boom", "input": {}}
        )
        assert "Exception" in result["content"]
        assert "Internal error" in result["content"]

    @pytest.mark.asyncio
    async def test_tool_no_output(self, monkeypatch):
        from dataclasses import dataclass

        @dataclass
        class MockResult:
            success: bool
            content: str
            error: str = ""

        async def mock_execute(name, **kwargs):
            return MockResult(success=True, content="")

        monkeypatch.setattr("harnessgenj_dev.core.agent.execute_tool", mock_execute)
        agent = Agent(MockLLMGateway())

        result = await agent._execute_tool_call(
            {"name": "write_file", "input": {"path": "x.py", "content": "x"}}
        )
        assert "no output" in result["content"].lower()


class TestAgentParseToolCalls:
    """Test _parse_tool_calls method."""

    def test_parse_from_tool_calls_field(self):
        agent = Agent(MockLLMGateway(), None)
        response = LLMResponse(
            content="",
            tool_calls=[{"name": "read", "input": {"path": "a.py"}}],
        )
        calls = agent._parse_tool_calls(response)
        assert len(calls) == 1
        assert calls[0]["name"] == "read"

    def test_parse_from_content_regex(self):
        agent = Agent(MockLLMGateway(), None)
        response = LLMResponse(
            content='I will read the file.\n```tool:read_file\n{"path": "test.py"}\n```\nDone.'
        )
        calls = agent._parse_tool_calls(response)
        assert len(calls) == 1
        assert calls[0]["name"] == "read_file"
        assert calls[0]["input"]["path"] == "test.py"

    def test_parse_invalid_json_in_content(self):
        agent = Agent(MockLLMGateway(), None)
        response = LLMResponse(
            content='```tool:read_file\n{invalid json}\n```'
        )
        calls = agent._parse_tool_calls(response)
        assert len(calls) == 0  # Invalid JSON should be skipped

    def test_parse_multiple_tool_calls_in_content(self):
        agent = Agent(MockLLMGateway(), None)
        response = LLMResponse(
            content='First: ```tool:read\n{"f":"a"}\n``` Second: ```tool:write\n{"f":"b"}\n```'
        )
        calls = agent._parse_tool_calls(response)
        assert len(calls) == 2


class TestAgentBuildSystemPrompt:
    """Test _build_system_prompt method."""

    def test_build_prompt_default_role(self):
        agent = Agent(MockLLMGateway(), None)
        prompt = agent._build_system_prompt()
        assert "AI-driven development framework" in prompt

    def test_build_prompt_developer_role(self):
        agent = Agent(MockLLMGateway(), None)
        prompt = agent._build_system_prompt("developer")
        assert "SOLID" in prompt

    def test_build_prompt_code_reviewer_role(self):
        agent = Agent(MockLLMGateway(), None)
        prompt = agent._build_system_prompt("code_reviewer")
        assert "security" in prompt.lower()

    def test_build_prompt_unknown_role(self):
        agent = Agent(MockLLMGateway(), None)
        prompt = agent._build_system_prompt("nonexistent_role")
        assert "Help users" in prompt

    def test_build_prompt_empty_tool_registry(self):
        agent = Agent(MockLLMGateway(), tool_registry=None)
        prompt = agent._build_system_prompt()
        assert "No tools available" in prompt

    def test_build_prompt_with_config_project_path(self):
        import platform
        class MockConfig:
            project_path = "/my/project"

        agent = Agent(MockLLMGateway(), config=MockConfig())
        prompt = agent._build_system_prompt()
        # On Windows, /my/project resolves to C:\my\project
        if platform.system() == "Windows":
            assert "my\\project" in prompt
        else:
            assert "/my/project" in prompt


class TestAgentStream:
    """Test run_stream method."""

    @pytest.mark.asyncio
    async def test_run_stream_yields_content(self):
        from harnessgenj_dev.llm.models import StreamChunk

        gateway = MockLLMGateway()
        gateway.stream_chunks = [
            StreamChunk(content="Hello", done=False),
            StreamChunk(content=" world", done=True),
        ]
        reg = MockToolRegistry()
        agent = Agent(gateway, reg)

        chunks = []
        async for chunk in agent.run_stream("hi"):
            chunks.append(chunk)
        assert "Hello" in "".join(chunks)
        assert "world" in "".join(chunks)

    @pytest.mark.asyncio
    async def test_run_stream_error_recovery(self):
        gateway = MockLLMGateway()

        async def failing_stream(messages, tools=None, **kwargs):
            raise ConnectionError("Stream failed")
            yield  # Make it a generator

        gateway.stream = failing_stream
        reg = MockToolRegistry()
        agent = Agent(gateway, reg)

        chunks = []
        async for chunk in agent.run_stream("hi"):
            chunks.append(chunk)
        # Should yield error message
        assert any("Error" in c for c in chunks)

    @pytest.mark.asyncio
    async def test_run_stream_max_iterations(self):
        """Streaming should also stop at max iterations."""
        from harnessgenj_dev.llm.models import StreamChunk

        gateway = MockLLMGateway()
        # Tool call triggers second iteration
        gateway.stream_chunks = [
            StreamChunk(content="```tool:read\n{}\n```", done=True),
            StreamChunk(content="Still working", done=True),
        ]
        reg = MockToolRegistry()
        agent = Agent(gateway, reg)
        agent.state.max_iterations = 2

        chunks = []
        async for chunk in agent.run_stream("test"):
            chunks.append(chunk)
        # Should complete within max iterations
        assert len(chunks) > 0


class TestAgentInterrupt:
    """Test interrupt method."""

    def test_interrupt_stops_execution(self):
        agent = Agent(MockLLMGateway(), None)
        agent.state.is_running = True
        agent.interrupt()
        assert agent.state.is_running is False


class TestAgentState:
    """Test AgentState dataclass."""

    def test_create_state(self):
        state = AgentState()
        # Default value in AgentState dataclass is 20, but Agent overrides based on effort
        assert state.max_iterations == 20
        assert state.iteration_count == 0
        assert state.is_running is False
        assert state.conversation_history == []


class TestThoughtAction:
    """Test ThoughtAction dataclass."""

    def test_create_thought_only(self):
        ta = ThoughtAction(thought="I should read the file first")
        assert ta.tool_name is None
        assert ta.tool_args is None

    def test_create_thought_with_action(self):
        ta = ThoughtAction(
            thought="Read the config file",
            tool_name="read_file",
            tool_args={"path": "config.py"},
        )
        assert ta.tool_name == "read_file"
        assert ta.tool_args["path"] == "config.py"
