"""Tests for HGJ integration with mocked Harness."""

import pytest
from unittest.mock import MagicMock, patch


class TestHGJIntegrationHarnessAvailable:
    """Test integration when HGJ Harness IS available."""

    def test_setup_harness_success(self):
        mock_harness = MagicMock()
        with patch("harnessgenj.Harness", return_value=mock_harness):
            from harnessgenj_dev.hgj.integration import HGJIntegration
            integration = HGJIntegration()
            integration.setup_harness("My Project")
            assert integration.harness_available is True

    def test_setup_harness_import_error(self):
        with patch("harnessgenj.Harness", side_effect=ImportError("not found")):
            from harnessgenj_dev.hgj.integration import HGJIntegration
            integration = HGJIntegration()
            integration.setup_harness("My Project")
            assert integration.harness_available is False

    def test_setup_harness_general_exception(self):
        with patch("harnessgenj.Harness", side_effect=RuntimeError("fail")):
            from harnessgenj_dev.hgj.integration import HGJIntegration
            integration = HGJIntegration()
            integration.setup_harness("My Project")
            assert integration.harness_available is False

    @pytest.mark.asyncio
    async def test_develop_harness_path(self):
        mock_harness = MagicMock()
        mock_harness.develop.return_value = {"task_id": "dev-1", "instruction": "test", "permitted_files": [], "status": "instruction"}
        with patch("harnessgenj.Harness", return_value=mock_harness):
            from harnessgenj_dev.hgj.integration import HGJIntegration
            integration = HGJIntegration()
            integration.setup_harness("Test")
            result = await integration.develop("user login")
            assert result.success is True
            assert result.task_id == "dev-1"
            assert result.metadata["source"] == "harness"

    @pytest.mark.asyncio
    async def test_fix_bug_harness_path(self):
        mock_harness = MagicMock()
        mock_harness.fix_bug.return_value = {"task_id": "fix-1", "instruction": "test", "permitted_files": [], "status": "instruction"}
        with patch("harnessgenj.Harness", return_value=mock_harness):
            from harnessgenj_dev.hgj.integration import HGJIntegration
            integration = HGJIntegration()
            integration.setup_harness("Test")
            result = await integration.fix_bug("null pointer in auth")
            assert result.success is True
            assert result.task_id == "fix-1"
            assert result.metadata["source"] == "harness"

    @pytest.mark.asyncio
    async def test_review_harness_path_code_content(self):
        mock_harness = MagicMock()
        mock_harness.quick_review.return_value = (True, ["Looks good"])
        with patch("harnessgenj.Harness", return_value=mock_harness):
            from harnessgenj_dev.hgj.integration import HGJIntegration
            integration = HGJIntegration()
            integration.setup_harness("Test")
            result = await integration.review("def foo(): pass")
            assert result.success is True
            assert result.metadata["source"] == "harness"
            assert result.metadata["passed"] is True

    @pytest.mark.asyncio
    async def test_review_harness_path_with_file(self, tmp_path):
        """Review should detect file path and read content."""
        code_file = tmp_path / "test_code.py"
        code_file.write_text("def foo():\n    return error\n")

        mock_harness = MagicMock()
        mock_harness.quick_review.return_value = (False, ["Found error in code"])
        with patch("harnessgenj.Harness", return_value=mock_harness):
            from harnessgenj_dev.hgj.integration import HGJIntegration
            integration = HGJIntegration()
            integration.setup_harness("Test")
            result = await integration.review(str(code_file))
            assert result.metadata["source"] == "harness"
            assert result.metadata["passed"] is False

    @pytest.mark.asyncio
    async def test_review_harness_file_not_found(self):
        mock_harness = MagicMock()
        with patch("harnessgenj.Harness", return_value=mock_harness):
            from harnessgenj_dev.hgj.integration import HGJIntegration
            integration = HGJIntegration()
            integration.setup_harness("Test")
            result = await integration.review("/nonexistent_file_xyz.py")
            # Should handle gracefully (file not found -> review placeholder code)
            from harnessgenj_dev.hgj.integration import HGJDevResult
            assert isinstance(result, HGJDevResult)

    @pytest.mark.asyncio
    async def test_adversarial_develop_harness_path(self):
        mock_harness = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.rounds = 2
        mock_result.quality_score = 85.0
        mock_harness.adversarial_develop.return_value = mock_result
        with patch("harnessgenj.Harness", return_value=mock_harness):
            from harnessgenj_dev.hgj.integration import HGJIntegration
            integration = HGJIntegration()
            integration.setup_harness("Test")
            result = await integration.adversarial_develop("payment feature", max_rounds=2, use_hunter=False)
            assert result.success is True
            assert result.metadata["source"] == "harness_adversarial"

    def test_get_status_harness_available(self):
        mock_harness = MagicMock()
        mock_harness.get_status.return_value = {"project": "Test", "tasks": 1}
        with patch("harnessgenj.Harness", return_value=mock_harness):
            from harnessgenj_dev.hgj.integration import HGJIntegration
            integration = HGJIntegration()
            integration.setup_harness("Test")
            status = integration.get_status()
            assert status["project"] == "Test"

    def test_get_status_harness_exception(self):
        mock_harness = MagicMock()
        mock_harness.get_status.side_effect = RuntimeError("Broken")
        with patch("harnessgenj.Harness", return_value=mock_harness):
            from harnessgenj_dev.hgj.integration import HGJIntegration
            integration = HGJIntegration()
            integration.setup_harness("Test")
            status = integration.get_status()
            assert "error" in status

    def test_get_context_harness_available(self):
        mock_harness = MagicMock()
        mock_harness.get_context_prompt.return_value = "Context for code_reviewer (max 4000 tokens)"
        with patch("harnessgenj.Harness", return_value=mock_harness):
            from harnessgenj_dev.hgj.integration import HGJIntegration
            integration = HGJIntegration()
            integration.setup_harness("Test")
            ctx = integration.get_context("code_reviewer")
            assert "code_reviewer" in ctx

    def test_receive_request_harness_available(self):
        mock_harness = MagicMock()
        mock_harness.receive_request.return_value = {"task_id": "req-1", "priority": "high", "assignee": "developer"}
        with patch("harnessgenj.Harness", return_value=mock_harness):
            from harnessgenj_dev.hgj.integration import HGJIntegration
            integration = HGJIntegration()
            integration.setup_harness("Test")
            result = integration.receive_request("need login feature")
            assert result.success is True
            assert result.task_id == "req-1"
            assert result.role == "project_manager"

    def test_complete_task_harness_available(self):
        mock_harness = MagicMock()
        mock_harness.complete_task.return_value = True
        with patch("harnessgenj.Harness", return_value=mock_harness):
            from harnessgenj_dev.hgj.integration import HGJIntegration
            integration = HGJIntegration()
            integration.setup_harness("Test")
            # First create a task
            mock_harness.receive_request.return_value = {"task_id": "req-1", "priority": "high", "assignee": "developer"}
            integration.receive_request("test")
            result = integration.complete_task("req-1", "done")
            assert result is True

    def test_complete_task_harness_exception(self):
        mock_harness = MagicMock()
        mock_harness.complete_task.side_effect = RuntimeError("fail")
        with patch("harnessgenj.Harness", return_value=mock_harness):
            from harnessgenj_dev.hgj.integration import HGJIntegration
            integration = HGJIntegration()
            integration.setup_harness("Test")
            result = integration.complete_task("task-1")
            assert result is False


class TestHGJIntegrationBuildAgent:
    """Test _build_agent method."""

    def test_build_agent_default_role(self):
        from harnessgenj_dev.hgj.integration import HGJIntegration
        integration = HGJIntegration()
        agent = integration._build_agent()
        assert agent is not None
        assert agent.config is None  # No config passed

    def test_build_agent_custom_role(self):
        from harnessgenj_dev.hgj.integration import HGJIntegration
        integration = HGJIntegration()
        agent = integration._build_agent(role="code_reviewer")
        assert agent is not None
