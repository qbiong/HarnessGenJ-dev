"""Phase State Machine — structured DISCUSS→PLAN→EXECUTE→VERIFY→SHIP flow.

ClawTeam-inspired design with Gate-based phase transitions:

    User → DISCUSS → PLAN → EXECUTE → VERIFY → SHIP
                     ↓         ↓         ↓        ↓
                   Spec     Code      Tests     Push
                   ADR      Files     Review    Deploy

Each phase has Gates that must pass before advancing.
Gates are checked deterministically — no LLM involvement.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# Phase constants
DISCUSS = "discuss"
PLAN = "plan"
EXECUTE = "execute"
VERIFY = "verify"
SHIP = "ship"

PHASE_ORDER = [DISCUSS, PLAN, EXECUTE, VERIFY, SHIP]

# Human-readable labels
PHASE_LABELS = {
    DISCUSS: "需求讨论",
    PLAN: "方案设计",
    EXECUTE: "编码实现",
    VERIFY: "质量验证",
    SHIP: "交付上线",
}

# Default role mapping for each phase
PHASE_ROLES = {
    DISCUSS: ["product_manager"],
    PLAN: ["architect"],
    EXECUTE: ["developer"],
    VERIFY: ["code_reviewer", "bug_hunter"],
    SHIP: ["doc_writer"],
}


class Gate(ABC):
    """A condition that must pass before a phase can advance."""

    @abstractmethod
    async def check(self, context: dict[str, Any]) -> tuple[bool, str]:
        """Return (passed, reason)."""


class ArtifactRequiredGate(Gate):
    """Requires specific artifacts/files to exist."""

    def __init__(self, file_paths: list[str]):
        self.file_paths = file_paths

    async def check(self, context: dict[str, Any]) -> tuple[bool, str]:
        import os
        proj_path = context.get("project_path", "")
        missing = []
        for fp in self.file_paths:
            full = os.path.join(proj_path, fp) if proj_path else fp
            if not os.path.exists(full):
                missing.append(fp)
        if missing:
            return False, f"Missing: {', '.join(missing)}"
        return True, ""


class TestPassGate(Gate):
    """Requires tests to pass."""

    def __init__(self, test_path: str = "tests/"):
        self.test_path = test_path

    async def check(self, context: dict[str, Any]) -> tuple[bool, str]:
        import asyncio
        import subprocess
        proj_path = context.get("project_path", "")
        if not proj_path:
            return False, "No project path"
        try:
            proc = await asyncio.create_subprocess_shell(
                f"python -m pytest {self.test_path} -x --tb=short -q 2>&1 | tail -3",
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=proj_path,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
            out = stdout.decode("utf-8", errors="replace")[-300:]
            if "PASSED" in out or "passed" in out or "failed" not in out.lower():
                return True, out
            return False, out
        except asyncio.TimeoutError:
            return False, "Tests timed out"
        except Exception as exc:
            return False, str(exc)


@dataclass
class PhaseState:
    """Current state of the phase machine."""

    current_phase: str = DISCUSS
    phase_history: list[dict[str, str]] = field(default_factory=list)
    gates: dict[str, list[Gate]] = field(default_factory=dict)

    def __post_init__(self):
        if not self.gates:
            # Default gates
            self.gates = {
                PLAN: [ArtifactRequiredGate([".project-knowledge/project_status.md"])],
                VERIFY: [TestPassGate()],
            }

    @property
    def phase_index(self) -> int:
        try:
            return PHASE_ORDER.index(self.current_phase)
        except ValueError:
            return 0

    @property
    def is_last_phase(self) -> bool:
        return self.phase_index >= len(PHASE_ORDER) - 1

    def next_phase(self) -> str | None:
        """Get the next phase in order."""
        idx = self.phase_index
        if idx < len(PHASE_ORDER) - 1:
            return PHASE_ORDER[idx + 1]
        return None

    async def can_advance(self, context: dict[str, Any]) -> tuple[bool, str]:
        """Check if all gates for the current phase pass."""
        phase_gates = self.gates.get(self.current_phase, [])
        for gate in phase_gates:
            ok, reason = await gate.check(context)
            if not ok:
                return False, reason
        return True, ""

    async def advance(self, context: dict[str, Any]) -> str | None:
        """Try to advance to the next phase. Returns new phase or None."""
        ok, reason = await self.can_advance(context)
        if not ok:
            return None
        next_p = self.next_phase()
        if next_p is None:
            return None
        self.phase_history.append({
            "from": self.current_phase,
            "to": next_p,
            "at": datetime.now(timezone.utc).isoformat(),
        })
        self.current_phase = next_p
        return next_p

    def get_roles_for_current_phase(self) -> list[str]:
        """Get recommended roles for the current phase."""
        return PHASE_ROLES.get(self.current_phase, [])

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_phase": self.current_phase,
            "phase_label": PHASE_LABELS.get(self.current_phase, self.current_phase),
            "phase_history": self.phase_history,
        }
