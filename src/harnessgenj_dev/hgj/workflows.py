"""HGJ Workflow Orchestration.

Orchestrates multi-role workflows, coordinating the HGJ roles
(Developer, CodeReviewer, BugHunter, etc.) through HGJ-dev's
Agent Core and LLM Gateway.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class WorkflowStatus(Enum):
    """Status of a workflow execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class WorkflowStep:
    """A single step in a workflow.

    Attributes:
        role: The HGJ role for this step.
        task: Description of the task to perform.
        status: Current execution status.
        result: Result from execution.
    """

    role: str
    task: str
    status: WorkflowStatus = WorkflowStatus.PENDING
    result: Any = None


@dataclass
class WorkflowResult:
    """Result of a complete workflow execution.

    Attributes:
        workflow_name: Name of the executed workflow.
        status: Overall workflow status.
        steps: Individual step results.
        errors: List of error messages.
    """

    workflow_name: str
    status: WorkflowStatus = WorkflowStatus.PENDING
    steps: list[WorkflowStep] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# Standard workflow definitions
CODE_REVIEW_WORKFLOW = [
    WorkflowStep(role="developer", task="Review the requested code changes"),
    WorkflowStep(role="code_reviewer", task="Perform thorough code review"),
    WorkflowStep(role="bug_hunter", task="Search for potential bugs"),
]

BUG_FIX_WORKFLOW = [
    WorkflowStep(role="bug_hunter", task="Diagnose and understand the bug"),
    WorkflowStep(role="developer", task="Implement the fix"),
    WorkflowStep(role="tester", task="Verify the fix with tests"),
    WorkflowStep(role="code_reviewer", task="Review the fix"),
]

FEATURE_WORKFLOW = [
    WorkflowStep(role="architect", task="Design the feature approach"),
    WorkflowStep(role="developer", task="Implement the feature"),
    WorkflowStep(role="tester", task="Test the new feature"),
    WorkflowStep(role="code_reviewer", task="Review the implementation"),
]

STANDARD_WORKFLOWS: dict[str, list[WorkflowStep]] = {
    "code_review": CODE_REVIEW_WORKFLOW,
    "bug_fix": BUG_FIX_WORKFLOW,
    "feature": FEATURE_WORKFLOW,
}


class WorkflowOrchestrator:
    """Orchestrate HGJ multi-role workflows.

    Coordinates role execution through HGJ-dev's Agent Core,
    managing the sequence of roles and collecting results.
    """

    def __init__(self) -> None:
        """Initialize with standard workflow definitions."""
        self._workflows: dict[str, list[WorkflowStep]] = dict(STANDARD_WORKFLOWS)

    def list_workflows(self) -> list[str]:
        """Get names of all registered workflows.

        Returns:
            List of workflow names.
        """
        return list(self._workflows.keys())

    def get_workflow(self, name: str) -> list[WorkflowStep] | None:
        """Get a workflow by name.

        Args:
            name: Workflow identifier.

        Returns:
            List of workflow steps, or None if not found.
        """
        steps = self._workflows.get(name)
        if steps is None:
            return None
        # Return copies to avoid mutation
        return [WorkflowStep(role=s.role, task=s.task) for s in steps]

    def register_workflow(self, name: str, steps: list[WorkflowStep]) -> None:
        """Register a custom workflow.

        Args:
            name: Workflow identifier.
            steps: Ordered list of workflow steps.
        """
        self._workflows[name] = steps
