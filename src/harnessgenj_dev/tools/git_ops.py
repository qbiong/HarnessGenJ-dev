"""Git operation tools."""

from __future__ import annotations

import subprocess
from typing import Any

from .base import BaseTool, ToolResult


def _run_git(*args: str, cwd: str | None = None) -> ToolResult:
    """Helper to run a git command."""
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=10,
        )
        if result.returncode == 0:
            return ToolResult(content=result.stdout.strip())
        return ToolResult(success=False, error=result.stderr.strip())
    except FileNotFoundError:
        return ToolResult(success=False, error="git not found")
    except subprocess.TimeoutExpired:
        return ToolResult(success=False, error="git command timed out")


class GitStatusTool(BaseTool):
    name = "git_status"
    description = "Show git status"
    parameters = {"type": "object", "properties": {}}

    async def execute(self, **kwargs: Any) -> ToolResult:
        return _run_git("status", "--short")


class GitDiffTool(BaseTool):
    name = "git_diff"
    description = "Show git diff"
    parameters = {
        "type": "object",
        "properties": {
            "staged": {"type": "boolean", "default": False},
        },
    }

    async def execute(self, staged: bool = False, **kwargs: Any) -> ToolResult:
        args = ["diff", "--stat"]
        if staged:
            args.insert(1, "--cached")
        return _run_git(*args)


class GitLogTool(BaseTool):
    name = "git_log"
    description = "Show git log"
    parameters = {
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "default": 10},
        },
    }

    async def execute(self, limit: int = 10, **kwargs: Any) -> ToolResult:
        return _run_git("log", f"-{limit}", "--oneline")
