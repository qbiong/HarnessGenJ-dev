"""Conductor — deterministic agent orchestration loop.

ClawTeam-inspired replacement for PM's ReAct loop during task execution.
The Conductor replaces LLM-driven "thinking" with a deterministic polling loop:

    1. Start phase → spawn agents → wait for completion → check gates
    2. If gates pass → advance to next phase
    3. If gates fail → report failure to user
    4. Loop until SHIP phase or error

The PM is only involved for:
    - Initial goal understanding (user message)
    - Final result summary
    - Error recovery

Gate checks are deterministic — no LLM involved in phase transitions.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from .contracts import SprintContract, SuccessCriterion
from .phases import PHASE_LABELS, PhaseState

logger = logging.getLogger(__name__)


class Conductor:
    """Deterministic agent orchestration loop.

    Usage:
        conductor = Conductor(
            goal="Implement user auth",
            project_path="/path/to/project",
            dispatch_fn=dispatch_callback,
            notify_fn=notify_callback,
        )
        result = await conductor.run()
    """

    def __init__(
        self,
        goal: str,
        project_path: str = "",
        dispatch_fn=None,  # async (role, goal, prev_results) -> str
        notify_fn=None,    # async (event_type, data) -> None
    ) -> None:
        self.goal = goal
        self.project_path = project_path
        self._dispatch = dispatch_fn
        self._notify = notify_fn
        self._phase_state = PhaseState()
        self._results: dict[str, str] = {}

    async def _dispatch_phase_roles(self, phase: str) -> None:
        """Dispatch all roles for a given phase."""
        from ..memory.role_registry import list_roles
        from ..web.dashboard import _get_provider, _get_model, _get_api_key, _get_base_url

        phase_roles_map = {
            "plan": ["architect"],
            "execute": ["developer"],
            "verify": ["code_reviewer", "bug_hunter"],
            "ship": ["doc_writer"],
        }

        roles = phase_roles_map.get(phase, [])
        if not roles:
            return

        await self._fire("phase_start", {"phase": phase, "phase_label": PHASE_LABELS.get(phase, phase), "roles": roles})

        for role in roles:
            if self._dispatch:
                result = await self._dispatch(role, self.goal, self._results)
                self._results[role] = result or "(无输出)"

        await self._fire("phase_complete", {"phase": phase, "results": {r: self._results.get(r, "")[:100] for r in roles}})

    async def _fire(self, event: str, data: dict[str, Any]) -> None:
        """Fire a notification event."""
        if self._notify:
            try:
                await self._notify(event, data)
            except Exception:
                pass

    async def run(self) -> str:
        """Run the conductor loop through all phases.

        Returns a summary string suitable for PM synthesis.
        """
        await self._fire("conductor_start", {"goal": self.goal[:100]})

        while not self._phase_state.is_last_phase:
            phase = self._phase_state.current_phase
            logger.info("Conductor phase: %s (%s)", phase, PHASE_LABELS.get(phase, phase))

            # 1. Dispatch agents for this phase
            await self._dispatch_phase_roles(phase)

            # 2. Check gates and advance
            ctx = {
                "project_path": self.project_path,
                "agent_results": self._results,
            }
            new_phase = await self._phase_state.advance(ctx)

            if new_phase:
                logger.info("Conductor advanced: %s -> %s", phase, new_phase)
                await self._fire("phase_transition", {
                    "from_phase": phase,
                    "to_phase": new_phase,
                    "phase_label": PHASE_LABELS.get(new_phase, new_phase),
                })
            else:
                # Gate check failed — check which gate
                ok, reason = await self._phase_state.can_advance(ctx)
                error_msg = f"Phase {phase} blocked: {reason}"
                logger.warning("Conductor blocked: %s", error_msg)
                await self._fire("conductor_error", {"error": error_msg})
                break

        # Build summary
        lines = [
            "## Conductor 执行报告\n",
            f"**目标**: {self.goal[:200]}",
            f"**状态**: {'已完成' if self._phase_state.is_last_phase else '阻塞'}",
            "",
        ]
        for r, result in self._results.items():
            display = result[:200].replace("\n", " ")
            lines.append(f"- **{r}**: {display}...")

        return "\n".join(lines)
