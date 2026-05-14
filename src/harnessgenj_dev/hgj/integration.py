"""HGJ Integration Adapter.

Bridges the HGJ framework (Harness class, roles, workflows, quality system)
with HGJ-dev's Agent Core, LLM Gateway, and Tool Set.

Architecture:
    HGJ Harness.develop()  →  HGJ-dev Agent.run() driven execution
    HGJ Harness.fix_bug()  →  HGJ-dev Agent.run() with bug-fix workflow
    HGJ Harness.review()   →  HGJ-dev Agent.run() with review role
    HGJ Roles              →  System prompts for Agent
    HGJ Quality Gates      →  Validation after Agent actions
    HGJ Memory             →  Context injection for Agent
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from harnessgenj_dev.core.agent import Agent
from harnessgenj_dev.llm.gateway import LLMGateway

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Integration result types
# ---------------------------------------------------------------------------


@dataclass
class HGJDevResult:
    """Result from an HGJ-dev driven HGJ workflow.

    Attributes:
        success: Whether the workflow completed successfully.
        task_id: Unique task identifier (from HGJ).
        role: The HGJ role that executed the task.
        output: Text output from the agent.
        quality_score: Quality score from HGJ scoring system (if available).
        errors: List of error messages.
        metadata: Additional metadata from the execution.
    """

    success: bool
    task_id: str = ""
    role: str = ""
    output: str = ""
    quality_score: float | None = None
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# HGJ Integration Adapter
# ---------------------------------------------------------------------------


class HGJIntegration:
    """Bridge HGJ framework capabilities with HGJ-dev Agent Core.

    This adapter allows HGJ-dev to drive HGJ workflows through its
    Agent ReAct loop, combining:
    - HGJ's role system (Developer, CodeReviewer, etc.)
    - HGJ's workflow orchestration (pipelines, quality gates)
    - HGJ's memory system (context injection)
    - HGJ-dev's LLM Gateway (multi-model support)
    - HGJ-dev's Tool Set (file ops, shell, etc.)

    Usage:
        integration = HGJIntegration()
        result = await integration.develop("implement user login")
        result = await integration.fix_bug("null pointer in auth")
        result = await integration.review("src/auth.py")
    """

    def __init__(self, gateway: LLMGateway | None = None) -> None:
        """Initialize the integration.

        Args:
            gateway: Optional LLM gateway instance. Creates default if None.
        """
        self._gateway = gateway or LLMGateway()
        self._harness: Any | None = None

    def setup_harness(self, project_name: str = "HGJ-Dev Project", **kwargs: Any) -> None:
        """Initialize the HGJ Harness.

        Args:
            project_name: Name for the HGJ project.
            **kwargs: Additional kwargs passed to Harness constructor.
        """
        try:
            from harnessgenj import Harness

            self._harness = Harness(project_name, **kwargs)
            logger.info("HGJ Harness initialized for project: %s", project_name)
        except ImportError:
            logger.warning("harnessgenj package not installed. HGJ integration features will be limited.")
            self._harness = None
        except Exception as exc:
            logger.error("Failed to initialize HGJ Harness: %s", exc)
            self._harness = None

    @property
    def harness_available(self) -> bool:
        """Whether the HGJ Harness is available."""
        return self._harness is not None

    def _build_agent(self, role: str = "developer") -> Agent:
        """Build an Agent configured for a specific HGJ role.

        Args:
            role: HGJ role name.

        Returns:
            Configured Agent instance.
        """
        return Agent(
            llm_gateway=self._gateway,
        )

    async def develop(
        self,
        feature_request: str,
        role: str = "developer",
        max_iterations: int = 20,
    ) -> HGJDevResult:
        """Drive a feature development through the Agent.

        Uses HGJ's role system for context and HGJ-dev's Agent Core
        for execution.

        Args:
            feature_request: Description of the feature to implement.
            role: HGJ role to use (default: developer).
            max_iterations: Maximum Agent iterations.

        Returns:
            HGJDevResult with execution outcome.
        """
        # If HGJ Harness is available, use it directly
        if self._harness is not None:
            try:
                result = self._harness.develop(feature_request)
                return HGJDevResult(
                    success=True,
                    task_id=result.get("task_id", ""),
                    role=role,
                    output=str(result),
                    metadata={"source": "harness"},
                )
            except Exception as exc:
                logger.warning("HGJ Harness develop failed, using Agent: %s", exc)

        # Fallback to Agent-driven execution
        agent = self._build_agent(role)
        try:
            output = await agent.run(
                f"Implement the following feature: {feature_request}",
                max_iterations=max_iterations,
            )
            return HGJDevResult(
                success=True,
                role=role,
                output=output,
                metadata={"source": "agent"},
            )
        except Exception as exc:
            return HGJDevResult(
                success=False,
                role=role,
                errors=[str(exc)],
                metadata={"source": "agent"},
            )

    async def fix_bug(
        self,
        bug_description: str,
        role: str = "bug_hunter",
        max_iterations: int = 20,
    ) -> HGJDevResult:
        """Drive a bug fix through the Agent.

        Args:
            bug_description: Description of the bug.
            role: HGJ role to use (default: bug_hunter).
            max_iterations: Maximum Agent iterations.

        Returns:
            HGJDevResult with execution outcome.
        """
        # If HGJ Harness is available, use it directly
        if self._harness is not None:
            try:
                result = self._harness.fix_bug(bug_description)
                return HGJDevResult(
                    success=True,
                    task_id=result.get("task_id", ""),
                    role=role,
                    output=str(result),
                    metadata={"source": "harness"},
                )
            except Exception as exc:
                logger.warning("HGJ Harness fix_bug failed, using Agent: %s", exc)

        # Fallback to Agent-driven execution
        agent = self._build_agent(role)
        try:
            output = await agent.run(
                f"Fix the following bug: {bug_description}",
                max_iterations=max_iterations,
            )
            return HGJDevResult(
                success=True,
                role=role,
                output=output,
                metadata={"source": "agent"},
            )
        except Exception as exc:
            return HGJDevResult(
                success=False,
                role=role,
                errors=[str(exc)],
                metadata={"source": "agent"},
            )

    async def review(
        self,
        target: str,
        role: str = "code_reviewer",
        max_iterations: int = 15,
    ) -> HGJDevResult:
        """Drive a code review through the Agent.

        Args:
            target: File or code to review.
            role: HGJ role to use (default: code_reviewer).
            max_iterations: Maximum Agent iterations.

        Returns:
            HGJDevResult with execution outcome.
        """
        # If HGJ Harness is available, use quick_review
        if self._harness is not None:
            try:
                # Check if target is code content or file path
                if target.endswith(".py") or "/" in target:
                    # It's a file path — read and review
                    try:
                        with open(target, encoding="utf-8") as f:
                            code = f.read()
                    except FileNotFoundError:
                        code = f"# File not found: {target}"
                else:
                    code = target

                passed, comments = self._harness.quick_review(code)
                return HGJDevResult(
                    success=passed,
                    role=role,
                    output="\n".join(comments) if comments else "No issues found.",
                    metadata={"source": "harness", "passed": passed},
                )
            except Exception as exc:
                logger.warning("HGJ Harness review failed, using Agent: %s", exc)

        # Fallback to Agent-driven execution
        agent = self._build_agent(role)
        try:
            output = await agent.run(
                f"Review the following code/file: {target}",
                max_iterations=max_iterations,
            )
            return HGJDevResult(
                success=True,
                role=role,
                output=output,
                metadata={"source": "agent"},
            )
        except Exception as exc:
            return HGJDevResult(
                success=False,
                role=role,
                errors=[str(exc)],
                metadata={"source": "agent"},
            )

    async def adversarial_develop(
        self,
        feature_request: str,
        max_rounds: int = 3,
        use_hunter: bool = True,
    ) -> HGJDevResult:
        """Drive adversarial development through HGJ.

        Uses HGJ's built-in adversarial development loop if available,
        otherwise falls back to Agent-driven sequential review.

        Args:
            feature_request: Description of the feature.
            max_rounds: Maximum adversarial rounds.
            use_hunter: Whether to include BugHunter.

        Returns:
            HGJDevResult with execution outcome.
        """
        if self._harness is not None:
            try:
                result = self._harness.adversarial_develop(
                    feature_request,
                    max_rounds=max_rounds,
                    use_hunter=use_hunter,
                )
                return HGJDevResult(
                    success=getattr(result, "success", False),
                    role="developer+reviewer",
                    output=str(result),
                    metadata={"source": "harness_adversarial"},
                )
            except Exception as exc:
                logger.warning("HGJ adversarial_develop failed: %s", exc)

        return HGJDevResult(
            success=False,
            role="developer+reviewer",
            errors=["Adversarial development requires harnessgenj>=1.5.2"],
            metadata={"source": "not_available"},
        )

    def get_status(self) -> dict[str, Any]:
        """Get HGJ project status.

        Returns:
            Status dict from HGJ Harness or limited info.
        """
        if self._harness is not None:
            try:
                return self._harness.get_status()
            except Exception as exc:
                return {"error": str(exc), "harness": False}
        return {
            "harness": False,
            "version": "1.4.6",
            "message": "HGJ Harness not available",
        }

    def get_context(self, role: str = "developer", max_tokens: int = 4000) -> str:
        """Get assembled context for a role from HGJ.

        Args:
            role: HGJ role name.
            max_tokens: Maximum tokens in context.

        Returns:
            Context prompt string.
        """
        if self._harness is not None:
            try:
                return self._harness.get_context_prompt(role, max_tokens)
            except Exception:
                pass
        return f"Role: {role}\n(Context not available — HGJ Harness not initialized)"

    def receive_request(self, request: str, request_type: str = "feature") -> HGJDevResult:
        """Route a request through HGJ's PM workflow.

        Args:
            request: User request description.
            request_type: Type of request.

        Returns:
            HGJDevResult with routing outcome.
        """
        if self._harness is not None:
            try:
                result = self._harness.receive_request(request, request_type)
                return HGJDevResult(
                    success=True,
                    task_id=result.get("task_id", ""),
                    role="project_manager",
                    output=str(result),
                    metadata={"source": "harness"},
                )
            except Exception as exc:
                return HGJDevResult(
                    success=False,
                    role="project_manager",
                    errors=[str(exc)],
                )
        return HGJDevResult(
            success=False,
            role="project_manager",
            errors=["HGJ Harness not available"],
        )

    def complete_task(self, task_id: str, summary: str = "") -> bool:
        """Mark a task as complete in HGJ.

        Args:
            task_id: Task identifier.
            summary: Completion summary.

        Returns:
            True if task was marked complete.
        """
        if self._harness is not None:
            try:
                return self._harness.complete_task(task_id, summary)
            except Exception as exc:
                logger.error("Failed to complete task: %s", exc)
        return False
