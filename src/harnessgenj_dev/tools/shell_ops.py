"""Shell command execution tools."""

from __future__ import annotations

import asyncio
import subprocess
from typing import Any

from .base import BaseTool, ToolResult

MAX_OUTPUT_CHARS = 50_000


class RunCommandTool(BaseTool):
    """Execute a shell command."""

    name = "run_command"
    description = "Run a shell command with timeout"
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to execute"},
            "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 30},
            "cwd": {"type": "string", "description": "Working directory"},
        },
        "required": ["command"],
    }

    async def execute(self, command: str, timeout: int = 30, cwd: str | None = None, **kwargs: Any) -> ToolResult:
        # Default to user's project directory (Claude Code isolation pattern)
        if cwd is None:
            try:
                from harnessgenj_dev.projects import get_active_project
                active = get_active_project()
                if active and active.get("path"):
                    cwd = active["path"]
            except Exception:
                pass
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=cwd,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            out = stdout.decode("utf-8", errors="replace")
            err = stderr.decode("utf-8", errors="replace")

            result = ""
            if out:
                result += out[:MAX_OUTPUT_CHARS]
            if err:
                if result:
                    result += "\n--- STDERR ---\n"
                result += err[:MAX_OUTPUT_CHARS]

            if len(out) > MAX_OUTPUT_CHARS or len(err) > MAX_OUTPUT_CHARS:
                result += f"\n\n[Output truncated, exceeded {MAX_OUTPUT_CHARS} chars]"

            return ToolResult(
                success=proc.returncode == 0,
                content=result,
                metadata={"exit_code": proc.returncode},
            )
        except TimeoutError:
            return ToolResult(success=False, error=f"Command timed out after {timeout}s")
