"""Integration/mock end-to-end tests simulating full workflows."""

import json
import os
import tempfile

import pytest

from harnessgenj_dev.core.agent import Agent
from harnessgenj_dev.llm.gateway import LLMGateway
from harnessgenj_dev.llm.models import LLMResponse, StreamChunk
from harnessgenj_dev.tools.registry import auto_register, execute_tool, get_schemas
from harnessgenj_dev.hgj.roles import RoleManager
from harnessgenj_dev.hgj.workflows import WorkflowOrchestrator
from harnessgenj_dev.plugins.registry import PluginRegistry
from harnessgenj_dev.plugins.manager import PluginManager
from harnessgenj_dev.projects import ProjectManager


class MockGateway:
    """Mock gateway for integration testing."""

    def __init__(self) -> None:
        self.responses: list[LLMResponse] = []
        self.call_count: int = 0

    def set_responses(self, responses: list[LLMResponse]) -> None:
        self.responses = responses

    async def chat(self, messages, tools=None, **kwargs):
        self.call_count += 1
        if self.call_count <= len(self.responses):
            return self.responses[self.call_count - 1]
        return LLMResponse(content="Final answer.", model="mock")

    async def stream(self, messages, tools=None, **kwargs):
        self.call_count += 1
        for chunk in self.stream_items:
            yield chunk
        yield StreamChunk(content="", done=True)


class MockToolRegistry:
    """Mock tool registry for integration testing."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def execute(self, name, **kwargs):
        self.calls.append({"name": name, "args": kwargs})

        class Result:
            def __init__(self, success, content, error=""):
                self.success = success
                self.content = content
                self.error = error

        return Result(True, f"{name} executed with {kwargs}")


class TestAgentWithMockedGateway:
    """Test Agent with a fully mocked gateway end-to-end."""

    @pytest.mark.asyncio
    async def test_agent_full_react_loop(self, monkeypatch):
        """Full ReAct loop: user -> tool call -> tool result -> final answer."""
        gateway = MockGateway()
        gateway.set_responses([
            LLMResponse(
                content="Let me check the file",
                tool_calls=[{"name": "read_file", "input": {"path": "test.py"}}],
            ),
            LLMResponse(content="The file looks good. Task complete."),
        ])

        calls = []

        async def mock_execute_tool(name, **kwargs):
            calls.append({"name": name, "args": kwargs})

            class Result:
                def __init__(self, success, content, error=""):
                    self.success = success
                    self.content = content
                    self.error = error

            return Result(True, f"{name} executed with {kwargs}")

        async def mock_execute_tools_parallel(tool_calls):
            # tool_calls: [{"name": ..., "input": {...}}, ...]
            results = []
            for tc in tool_calls:
                calls.append({"name": tc.get("name", ""), "args": tc.get("input", {})})

                class Result:
                    def __init__(self, success, content, error=""):
                        self.success = success
                        self.content = content
                        self.error = error

                results.append(Result(True, f"{tc.get('name')} executed"))
            return results

        monkeypatch.setattr("harnessgenj_dev.core.agent.execute_tool", mock_execute_tool)
        monkeypatch.setattr("harnessgenj_dev.core.agent.execute_tools_parallel", mock_execute_tools_parallel)
        agent = Agent(gateway)

        result = await agent.run("Check test.py")
        assert "Task complete" in result
        assert gateway.call_count == 2
        assert len(calls) == 1
        assert calls[0]["name"] == "read_file"

    @pytest.mark.asyncio
    async def test_agent_multiple_tool_calls_in_sequence(self, monkeypatch):
        """Agent makes multiple tool calls across iterations."""
        gateway = MockGateway()
        gateway.set_responses([
            LLMResponse(
                content="Reading first",
                tool_calls=[{"name": "read_file", "input": {"path": "a.py"}}],
            ),
            LLMResponse(
                content="Writing now",
                tool_calls=[{"name": "write_file", "input": {"path": "b.py", "content": "x"}}],
            ),
            LLMResponse(content="All done."),
        ])

        calls = []

        async def mock_execute_tool(name, **kwargs):
            calls.append({"name": name, "args": kwargs})

            class Result:
                def __init__(self, success, content, error=""):
                    self.success = success
                    self.content = content
                    self.error = error

            return Result(True, f"{name} executed")

        async def mock_execute_tools_parallel(tool_calls):
            results = []
            for tc in tool_calls:
                calls.append({"name": tc.get("name", ""), "args": tc.get("input", {})})

                class Result:
                    def __init__(self, success, content, error=""):
                        self.success = success
                        self.content = content
                        self.error = error

                results.append(Result(True, f"{tc.get('name')} executed"))
            return results

        monkeypatch.setattr("harnessgenj_dev.core.agent.execute_tool", mock_execute_tool)
        monkeypatch.setattr("harnessgenj_dev.core.agent.execute_tools_parallel", mock_execute_tools_parallel)
        agent = Agent(gateway)

        result = await agent.run("Edit files")
        assert "All done" in result
        assert len(calls) == 2

    @pytest.mark.asyncio
    async def test_agent_llm_error_recovery(self, monkeypatch):
        """Agent should gracefully handle LLM errors."""
        gateway = MockGateway()

        async def failing_chat(messages, tools=None, **kwargs):
            raise ConnectionError("API unavailable")

        gateway.chat = failing_chat

        async def mock_execute_tool(name, **kwargs):
            class Result:
                def __init__(self, success, content, error=""):
                    self.success = success
                    self.content = content
                    self.error = error
            return Result(True, "ok")

        async def mock_execute_tools_parallel(tool_calls):
            return [Result(True, "ok") for _ in tool_calls]

        monkeypatch.setattr("harnessgenj_dev.core.agent.execute_tool", mock_execute_tool)
        monkeypatch.setattr("harnessgenj_dev.core.agent.execute_tools_parallel", mock_execute_tools_parallel)
        agent = Agent(gateway)

        result = await agent.run("test")
        assert "Error" in result
        assert agent.state.is_running is False


class TestHGJRolesAndWorkflowsIntegration:
    """Test HGJ roles and workflows together."""

    def test_role_to_system_prompt_in_agent(self):
        """Verify HGJ role can produce system prompt for Agent."""
        role_mgr = RoleManager()
        prompt = role_mgr.to_system_prompt("developer")
        assert len(prompt) > 0
        assert "software" in prompt.lower()

    def test_workflow_orchestrator_with_role_manager(self):
        """Verify workflow steps reference valid roles."""
        orch = WorkflowOrchestrator()
        role_mgr = RoleManager()

        for wf_name in orch.list_workflows():
            steps = orch.get_workflow(wf_name)
            assert steps is not None
            for step in steps:
                role = role_mgr.get_role(step.role)
                assert role is not None, f"Role '{step.role}' in workflow '{wf_name}' not found"

    def test_feature_workflow_all_roles_valid(self):
        orch = WorkflowOrchestrator()
        role_mgr = RoleManager()
        steps = orch.get_workflow("feature")
        assert steps is not None
        role_names = [s.role for s in steps]
        assert "architect" in role_names
        assert "developer" in role_names
        assert "tester" in role_names
        assert "code_reviewer" in role_names
        for role_name in role_names:
            assert role_mgr.get_role(role_name) is not None


class TestPluginManagerIntegration:
    """Test plugin manager with real plugin lifecycle."""

    @pytest.mark.asyncio
    async def test_plugin_manager_full_lifecycle(self):
        """Register -> initialize -> fire hook -> shutdown."""
        from harnessgenj_dev.plugins.base import Plugin, PluginInfo

        class TestPlugin(Plugin):
            info = PluginInfo(name="test-lifecycle", version="0.1.0")

            async def initialize(self, config=None):
                self._initialized = True

            async def shutdown(self):
                self._shutdown = True

            async def on_test_hook(self, **kwargs):
                return {"hook_fired": True}

            def get_hooks(self):
                return {"test_hook": self.on_test_hook}

        manager = PluginManager()
        manager.register(TestPlugin())
        await manager.initialize_all(configs={"test-lifecycle": {}})
        assert manager.is_initialized is True

        results = await manager.fire_hook("test_hook")
        assert any(r.get("hook_fired") for r in results if isinstance(r, dict))

        await manager.shutdown_all()
        assert manager.is_initialized is False


class TestProjectManagerWebIntegration:
    """Test project manager with file system operations."""

    def test_project_with_real_paths(self, tmp_path):
        """Test project creation with real directory paths."""
        project_dir = tmp_path / "my-project"
        project_dir.mkdir()

        pm = ProjectManager()
        pm.add_project("my-project", str(project_dir))
        assert pm.project_count == 1

        project = pm.get_project("my-project")
        assert project is not None
        assert os.path.isdir(project.path)

    def test_project_persistence_real_file(self, tmp_path):
        storage = str(tmp_path / "projects.json")
        pm = ProjectManager(storage_path=storage)
        pm.add_project("test", str(tmp_path))
        pm.switch_to("test")
        pm._save()

        assert os.path.exists(storage)
        with open(storage) as f:
            data = json.load(f)
        assert "_active" in data
        assert "test" in data


class TestDashboardWithRealFiles:
    """Test dashboard file browser with real files."""

    @pytest.mark.asyncio
    async def test_list_directory_real_files(self, tmp_path):
        from harnessgenj_dev.web.dashboard import create_app, set_file_root
        from httpx import AsyncClient, ASGITransport

        set_file_root(str(tmp_path))

        # Create some files
        (tmp_path / "file1.py").write_text("print('hello')")
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "file2.txt").write_text("content")

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/files")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["items"]) >= 2  # file1.py, subdir

    @pytest.mark.asyncio
    async def test_read_file_real_content(self, tmp_path):
        from harnessgenj_dev.web.dashboard import create_app, set_file_root
        from httpx import AsyncClient, ASGITransport

        set_file_root(str(tmp_path))
        content = "line 1\nline 2\nline 3\n"
        (tmp_path / "test.txt").write_text(content)

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/files/content", params={"path": "test.txt"})
            assert resp.status_code == 200
            data = resp.json()
            assert "line 1" in data["content"]
            assert data["total_lines"] >= 3

    @pytest.mark.asyncio
    async def test_search_files_real_results(self, tmp_path):
        from harnessgenj_dev.web.dashboard import create_app, set_file_root
        from httpx import AsyncClient, ASGITransport

        set_file_root(str(tmp_path))
        (tmp_path / "test_search.py").write_text("def test(): pass")
        (tmp_path / "readme.txt").write_text("readme")

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/files/search", params={"path": "", "pattern": "*.py"})
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["matches"]) >= 1
            assert any("test_search" in m for m in data["matches"])


class TestEndToEndMockWorkflow:
    """Full mock end-to-end workflow simulating user interaction."""

    @pytest.mark.asyncio
    async def test_mock_develop_workflow(self, monkeypatch):
        """Simulate: user requests feature -> agent reads file -> writes code -> done."""
        gateway = MockGateway()
        gateway.set_responses([
            LLMResponse(
                content="I'll check the existing code first.",
                tool_calls=[{"name": "read_file", "input": {"path": "main.py"}}],
            ),
            LLMResponse(
                content="Now I'll implement the feature.",
                tool_calls=[{"name": "write_file", "input": {"path": "main.py", "content": "def new_feature(): pass"}}],
            ),
            LLMResponse(content="Feature implemented successfully."),
        ])

        calls = []

        async def mock_execute_tool(name, **kwargs):
            calls.append({"name": name, "args": kwargs})

            class Result:
                def __init__(self, success, content, error=""):
                    self.success = success
                    self.content = content
                    self.error = error

            return Result(True, f"{name} executed")

        async def mock_execute_tools_parallel(tool_calls):
            results = []
            for tc in tool_calls:
                calls.append({"name": tc.get("name", ""), "args": tc.get("input", {})})

                class Result:
                    def __init__(self, success, content, error=""):
                        self.success = success
                        self.content = content
                        self.error = error

                results.append(Result(True, f"{tc.get('name')} executed"))
            return results

        monkeypatch.setattr("harnessgenj_dev.core.agent.execute_tool", mock_execute_tool)
        monkeypatch.setattr("harnessgenj_dev.core.agent.execute_tools_parallel", mock_execute_tools_parallel)
        agent = Agent(gateway)

        result = await agent.run("Add a new feature to main.py")
        assert "implemented" in result.lower()
        assert len(calls) == 2
        assert calls[0]["name"] == "read_file"
        assert calls[1]["name"] == "write_file"

    @pytest.mark.asyncio
    async def test_mock_code_review_workflow(self, monkeypatch):
        """Simulate: code review -> find issues -> report."""
        gateway = MockGateway()
        gateway.set_responses([
            LLMResponse(
                content="Reviewing code...",
                tool_calls=[{"name": "read_file", "input": {"path": "auth.py"}}],
            ),
            LLMResponse(
                content="Found issues:\n1. Missing error handling\n2. Hardcoded credentials",
            ),
        ])

        calls = []

        async def mock_execute_tool(name, **kwargs):
            calls.append({"name": name, "args": kwargs})

            class Result:
                def __init__(self, success, content, error=""):
                    self.success = success
                    self.content = content
                    self.error = error

            return Result(True, f"{name} executed")

        async def mock_execute_tools_parallel(tool_calls):
            results = []
            for tc in tool_calls:
                calls.append({"name": tc.get("name", ""), "args": tc.get("input", {})})

                class Result:
                    def __init__(self, success, content, error=""):
                        self.success = success
                        self.content = content
                        self.error = error

                results.append(Result(True, f"{tc.get('name')} executed"))
            return results

        monkeypatch.setattr("harnessgenj_dev.core.agent.execute_tool", mock_execute_tool)
        monkeypatch.setattr("harnessgenj_dev.core.agent.execute_tools_parallel", mock_execute_tools_parallel)
        agent = Agent(gateway)

        result = await agent.run("Review auth.py", role="code_reviewer")
        assert "issues" in result.lower()
        assert len(calls) == 1
