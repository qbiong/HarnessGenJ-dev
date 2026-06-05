"""Sprint Contracts — structured task specifications with verifiable success criteria.

ClawTeam-inspired design:
- Each SprintContract has a set of SuccessCriteria (description + test_command)
- After execution, each criterion is verified (pass/fail with evidence)
- Only contracts with all criteria passed are marked as completed

Usage:
    contract = SprintContract(
        title="Implement LogAnomalyDetector",
        success_criteria=[
            SuccessCriterion(
                description="LogAnomalyDetector class exists in src/detector/",
                test_command="python -c 'from src.detector.log_anomaly_detector import LogAnomalyDetector'"
            ),
            SuccessCriterion(
                description="All tests pass",
                test_command="python -m pytest tests/test_log_anomaly_detector.py -v --tb=short -q"
            ),
        ]
    )
    results = await contract.verify_all()
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SuccessCriterion:
    """A single testable success criterion."""

    description: str = ""
    test_command: str = ""  # shell command to auto-verify
    expected_file: str = ""  # expected output file (alternative to test_command)
    verified: bool = False
    verified_by: str = ""
    evidence: str = ""  # stdout/stderr from test_command
    error: str = ""


@dataclass
class SprintContract:
    """A unit of work with testable success criteria."""

    id: str = ""
    title: str = ""
    description: str = ""
    role: str = ""  # which role this contract is assigned to
    success_criteria: list[SuccessCriterion] = field(default_factory=list)
    status: str = "pending"  # pending | in_progress | completed | failed
    project_path: str = ""  # working directory for test commands

    def __post_init__(self) -> None:
        if not self.id:
            self.id = uuid.uuid4().hex[:8]

    async def verify_all(self) -> list[SuccessCriterion]:
        """Execute each criterion's test_command and update verified status."""
        results = []
        for criterion in self.success_criteria:
            verified = False
            evidence = ""
            error = ""

            if criterion.test_command:
                try:
                    proc = await asyncio.create_subprocess_shell(
                        criterion.test_command,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        cwd=self.project_path or None,
                    )
                    stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
                    evidence = stdout.decode("utf-8", errors="replace")[-500:]
                    verified = proc.returncode == 0
                except asyncio.TimeoutError:
                    error = "Timed out after 60s"
                except Exception as exc:
                    error = str(exc)

            if criterion.expected_file and not criterion.test_command:
                file_path = Path(self.project_path) / criterion.expected_file if self.project_path else Path(criterion.expected_file)
                verified = file_path.exists()
                evidence = f"File exists: {file_path}" if verified else f"File not found: {file_path}"

            criterion.verified = verified
            criterion.evidence = evidence[:300] if evidence else ""
            criterion.error = error[:200] if error else ""
            results.append(criterion)

        # Update overall status
        if all(c.verified for c in self.success_criteria):
            self.status = "completed"
        elif any(c.verified for c in self.success_criteria):
            self.status = "in_progress"
        else:
            self.status = "failed"

        return results

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "role": self.role,
            "status": self.status,
            "criteria": [
                {
                    "description": c.description,
                    "verified": c.verified,
                    "evidence": c.evidence[:100],
                    "error": c.error[:100],
                }
                for c in self.success_criteria
            ],
        }

    def summary(self) -> str:
        """Return a concise markdown summary for PM synthesis."""
        total = len(self.success_criteria)
        passed = sum(1 for c in self.success_criteria if c.verified)
        lines = [
            f"### Contract: {self.title}",
            f"**Status**: {self.status} ({passed}/{total} criteria passed)",
        ]
        for c in self.success_criteria:
            icon = "✅" if c.verified else "❌"
            lines.append(f"- {icon} {c.description}")
            if c.evidence:
                lines.append(f"  ```{c.evidence[:100]}```")
        return "\n".join(lines)
