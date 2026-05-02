"""Tests for HGJ workflows module."""

import pytest

from harnessgenj_dev.hgj.workflows import (
    WorkflowStatus,
    WorkflowStep,
    WorkflowResult,
    CODE_REVIEW_WORKFLOW,
    BUG_FIX_WORKFLOW,
    FEATURE_WORKFLOW,
    STANDARD_WORKFLOWS,
    WorkflowOrchestrator,
)


class TestWorkflowStatus:
    """Test WorkflowStatus enum."""

    def test_enum_values(self):
        assert WorkflowStatus.PENDING.value == "pending"
        assert WorkflowStatus.RUNNING.value == "running"
        assert WorkflowStatus.COMPLETED.value == "completed"
        assert WorkflowStatus.FAILED.value == "failed"
        assert WorkflowStatus.CANCELLED.value == "cancelled"


class TestWorkflowStep:
    """Test WorkflowStep dataclass."""

    def test_create_step(self):
        step = WorkflowStep(role="developer", task="Write code")
        assert step.role == "developer"
        assert step.task == "Write code"
        assert step.status == WorkflowStatus.PENDING
        assert step.result is None

    def test_create_step_with_result(self):
        step = WorkflowStep(
            role="tester",
            task="Run tests",
            status=WorkflowStatus.COMPLETED,
            result="All tests passed",
        )
        assert step.status == WorkflowStatus.COMPLETED
        assert step.result == "All tests passed"


class TestWorkflowResult:
    """Test WorkflowResult dataclass."""

    def test_create_result(self):
        result = WorkflowResult(workflow_name="feature")
        assert result.workflow_name == "feature"
        assert result.status == WorkflowStatus.PENDING
        assert result.steps == []
        assert result.errors == []

    def test_create_result_with_steps(self):
        step = WorkflowStep(role="dev", task="code")
        result = WorkflowResult(
            workflow_name="bug_fix",
            status=WorkflowStatus.COMPLETED,
            steps=[step],
            errors=["Minor issue"],
        )
        assert len(result.steps) == 1
        assert len(result.errors) == 1


class TestStandardWorkflows:
    """Test standard workflow definitions."""

    def test_code_review_workflow(self):
        assert len(CODE_REVIEW_WORKFLOW) == 3
        assert CODE_REVIEW_WORKFLOW[0].role == "developer"
        assert CODE_REVIEW_WORKFLOW[1].role == "code_reviewer"
        assert CODE_REVIEW_WORKFLOW[2].role == "bug_hunter"

    def test_bug_fix_workflow(self):
        assert len(BUG_FIX_WORKFLOW) == 4
        assert BUG_FIX_WORKFLOW[0].role == "bug_hunter"
        assert BUG_FIX_WORKFLOW[1].role == "developer"
        assert BUG_FIX_WORKFLOW[2].role == "tester"
        assert BUG_FIX_WORKFLOW[3].role == "code_reviewer"

    def test_feature_workflow(self):
        assert len(FEATURE_WORKFLOW) == 4
        assert FEATURE_WORKFLOW[0].role == "architect"
        assert FEATURE_WORKFLOW[1].role == "developer"
        assert FEATURE_WORKFLOW[2].role == "tester"
        assert FEATURE_WORKFLOW[3].role == "code_reviewer"

    def test_standard_workflows_dict(self):
        assert "code_review" in STANDARD_WORKFLOWS
        assert "bug_fix" in STANDARD_WORKFLOWS
        assert "feature" in STANDARD_WORKFLOWS
        assert len(STANDARD_WORKFLOWS) == 3


class TestWorkflowOrchestrator:
    """Test WorkflowOrchestrator class."""

    def test_create_orchestrator(self):
        orch = WorkflowOrchestrator()
        assert orch is not None

    def test_list_workflows(self):
        orch = WorkflowOrchestrator()
        names = orch.list_workflows()
        assert "code_review" in names
        assert "bug_fix" in names
        assert "feature" in names
        assert len(names) == 3

    def test_get_existing_workflow(self):
        orch = WorkflowOrchestrator()
        steps = orch.get_workflow("code_review")
        assert steps is not None
        assert len(steps) == 3
        assert steps[0].role == "developer"

    def test_get_unknown_workflow(self):
        orch = WorkflowOrchestrator()
        assert orch.get_workflow("nonexistent") is None

    def test_get_workflow_returns_copies(self):
        """Modifying returned steps should not affect the original."""
        orch = WorkflowOrchestrator()
        steps1 = orch.get_workflow("bug_fix")
        steps2 = orch.get_workflow("bug_fix")
        assert steps1 is not steps2
        # Modifying one should not affect the other
        steps1[0].role = "modified"
        assert steps2[0].role == "bug_hunter"

    def test_register_custom_workflow(self):
        orch = WorkflowOrchestrator()
        steps = [
            WorkflowStep(role="dev", task="Implement"),
            WorkflowStep(role="test", task="Verify"),
        ]
        orch.register_workflow("custom", steps)
        assert "custom" in orch.list_workflows()
        retrieved = orch.get_workflow("custom")
        assert retrieved is not None
        assert len(retrieved) == 2

    def test_register_workflow_overwrites(self):
        orch = WorkflowOrchestrator()
        old = orch.get_workflow("feature")
        new_steps = [WorkflowStep(role="solo", task="Do everything")]
        orch.register_workflow("feature", new_steps)
        retrieved = orch.get_workflow("feature")
        assert len(retrieved) == 1
        assert retrieved[0].role == "solo"

    def test_get_workflow_step_status(self):
        orch = WorkflowOrchestrator()
        steps = orch.get_workflow("feature")
        for step in steps:
            assert step.status == WorkflowStatus.PENDING

    def test_get_workflow_step_result_none(self):
        orch = WorkflowOrchestrator()
        steps = orch.get_workflow("bug_fix")
        for step in steps:
            assert step.result is None
