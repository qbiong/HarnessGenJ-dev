"""Test execution tools."""

from __future__ import annotations

import asyncio
import subprocess
from typing import Any

from .base import BaseTool, ToolResult


class RunTestTool(BaseTool):
    """Run tests using pytest."""

    name = "run_test"
    description = "Run tests with pytest"
    parameters = {
        "type": "object",
        "properties": {
            "test_path": {"type": "string", "description": "Test file or directory"},
            "filter": {"type": "string", "description": "pytest -k filter expression"},
        },
    }

    async def execute(self, test_path: str = "tests", filter: str | None = None, **kwargs: Any) -> ToolResult:
        cmd = ["python", "-m", "pytest", test_path, "-v"]
        if filter:
            cmd.extend(["-k", filter])

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
            out = stdout.decode("utf-8", errors="replace")
            err = stderr.decode("utf-8", errors="replace")

            return ToolResult(
                success=proc.returncode == 0,
                content=(out + "\n" + err).strip()[:20_000],
                metadata={"exit_code": proc.returncode},
            )
        except TimeoutError:
            return ToolResult(success=False, error="Test execution timed out")
