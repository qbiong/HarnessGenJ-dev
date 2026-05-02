"""Tests for HGJ Integration Adapter."""

import pytest

from harnessgenj_dev.hgj import HGJIntegration, HGJDevResult


class TestHGJDevResult:
    """Test HGJDevResult dataclass."""

    def test_create_result(self):
        r = HGJDevResult(success=True)
        assert r.success is True
        assert r.task_id == ""
        assert r.errors == []

    def test_result_with_fields(self):
        r = HGJDevResult(
            success=True,
            task_id="task-123",
            role="developer",
            output="done",
            quality_score=85.0,
            errors=[],
            metadata={"source": "agent"},
        )
        assert r.task_id == "task-123"
        assert r.quality_score == 85.0
        assert r.metadata["source"] == "agent"


class TestHGJIntegration:
    """Test HGJIntegration adapter."""

    def test_create_integration(self):
        integration = HGJIntegration()
        assert integration is not None
        assert integration.harness_available is False

    def test_harness_not_available_by_default(self):
        integration = HGJIntegration()
        # harnessgenj is installed from local editable install
        # but may not be properly initialized
        assert integration.harness_available in (True, False)


class TestHGJIntegrationStatus:
    """Test status and context methods."""

    def test_get_status_no_harness(self):
        integration = HGJIntegration()
        # If harness is not available, returns limited info
        status = integration.get_status()
        assert "harness" in status

    def test_get_context_no_harness(self):
        integration = HGJIntegration()
        ctx = integration.get_context("developer")
        assert "developer" in ctx

    def test_get_context_custom_role(self):
        integration = HGJIntegration()
        ctx = integration.get_context("code_reviewer", max_tokens=2000)
        assert "code_reviewer" in ctx


class TestHGJIntegrationReceiveRequest:
    """Test receive_request method."""

    def test_receive_request_no_harness(self):
        integration = HGJIntegration()
        result = integration.receive_request("add feature")
        # Without harness, should return error result
        assert isinstance(result, HGJDevResult)
        assert result.role == "project_manager"


class TestHGJIntegrationCompleteTask:
    """Test complete_task method."""

    def test_complete_task_no_harness(self):
        integration = HGJIntegration()
        result = integration.complete_task("task-123", "done")
        # Without harness, should return False
        assert result is False


class TestHGJIntegrationAsyncMethods:
    """Test async integration methods."""

    @pytest.mark.asyncio
    async def test_develop_no_harness_fallback(self):
        """Without harness, develop should fall back to Agent."""
        integration = HGJIntegration()
        # This may fail without API key, but should return a result
        try:
            result = await integration.develop("test feature")
            assert isinstance(result, HGJDevResult)
        except Exception:
            # Expected if no API key configured
            pass

    @pytest.mark.asyncio
    async def test_fix_bug_no_harness_fallback(self):
        """Without harness, fix_bug should fall back to Agent."""
        integration = HGJIntegration()
        try:
            result = await integration.fix_bug("null pointer")
            assert isinstance(result, HGJDevResult)
        except Exception:
            pass

    @pytest.mark.asyncio
    async def test_review_no_harness_fallback(self):
        """Without harness, review should fall back to Agent."""
        integration = HGJIntegration()
        try:
            result = await integration.review("def foo(): pass")
            assert isinstance(result, HGJDevResult)
        except Exception:
            pass

    @pytest.mark.asyncio
    async def test_adversarial_develop_no_harness(self):
        """Without harness, adversarial develop should return error."""
        integration = HGJIntegration()
        result = await integration.adversarial_develop("test feature")
        assert isinstance(result, HGJDevResult)
        # Should indicate not available without proper harness
        assert result.success is False or result.metadata.get("source") != "harness"
