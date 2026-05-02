"""Code search and analysis tools."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

from .base import BaseTool, ToolResult

MAX_OUTPUT_CHARS = 20_000


class SearchCodeTool(BaseTool):
    """Search code using ripgrep with fallback to Python regex."""

    name = "search_code"
    description = "Search codebase with ripgrep (with Python regex fallback)"
    read_only = True  # 只读工具，可并行执行
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search pattern"},
            "file_pattern": {"type": "string", "description": "File glob filter (e.g. '*.py')"},
            "path": {"type": "string", "description": "Directory to search in"},
            "context": {"type": "integer", "description": "Lines of context before and after", "default": 0},
            "case_sensitive": {"type": "boolean", "description": "Case sensitive search", "default": False},
            "word_boundary": {"type": "boolean", "description": "Match whole words only", "default": False},
        },
        "required": ["query"],
    }

    def __init__(self) -> None:
        self._has_ripgrep: bool | None = None

    def _check_ripgrep(self) -> bool:
        """Check if ripgrep is available."""
        if self._has_ripgrep is None:
            try:
                subprocess.run(["rg", "--version"], capture_output=True, timeout=5)
                self._has_ripgrep = True
            except (FileNotFoundError, subprocess.TimeoutExpired):
                self._has_ripgrep = False
        return self._has_ripgrep

    async def execute(
        self,
        query: str,
        file_pattern: str | None = None,
        path: str = ".",
        context: int = 0,
        case_sensitive: bool = False,
        word_boundary: bool = False,
        **kwargs: Any,
    ) -> ToolResult:
        if word_boundary:
            query = rf"\b{query}\b"

        if self._check_ripgrep():
            return self._search_with_ripgrep(query, file_pattern, path, context, case_sensitive)
        return await self._search_with_python(query, file_pattern, path, context, case_sensitive, word_boundary)

    def _search_with_ripgrep(
        self,
        query: str,
        file_pattern: str | None,
        path: str,
        context: int,
        case_sensitive: bool,
    ) -> ToolResult:
        cmd = ["rg", "--color", "never", "--no-heading", "--line-number"]
        if file_pattern:
            cmd.extend(["--glob", file_pattern])
        if context > 0:
            cmd.extend(["--context", str(context)])
        if case_sensitive:
            cmd.append("--case-sensitive")
        cmd.extend([query, path])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                output = result.stdout[:MAX_OUTPUT_CHARS]
                if len(result.stdout) > MAX_OUTPUT_CHARS:
                    output += f"\n\n[Output truncated, exceeded {MAX_OUTPUT_CHARS} chars]"
                return ToolResult(content=output)
            elif result.returncode == 1:
                return ToolResult(content="No matches found")
            else:
                return ToolResult(success=False, error=result.stderr[:1000])
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, error="Search timed out")

    async def _search_with_python(
        self,
        query: str,
        file_pattern: str | None,
        path: str,
        context: int,
        case_sensitive: bool,
        word_boundary: bool,
    ) -> ToolResult:
        """Fallback search using Python regex when ripgrep is not available."""
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            pattern = re.compile(query, flags)
        except re.error as e:
            return ToolResult(success=False, error=f"Invalid regex: {e}")

        results = []
        search_path = Path(path)
        if not search_path.exists():
            return ToolResult(success=False, error=f"Path not found: {path}")

        for file_path in search_path.rglob("*"):
            if not file_path.is_file():
                continue
            if file_pattern:
                import fnmatch
                if not fnmatch.fnmatch(file_path.name, file_pattern):
                    continue
            try:
                lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
            except (PermissionError, OSError):
                continue

            for i, line in enumerate(lines):
                if pattern.search(line):
                    start = max(0, i - context)
                    end = min(len(lines), i + context + 1)
                    context_lines = lines[start:end]
                    prefix = f"{file_path}:{i + 1}"
                    results.append(f"{prefix} {'-' * 40}")
                    for j, ctx_line in enumerate(context_lines):
                        line_num = start + j + 1
                        marker = ">" if j == context else " "
                        results.append(f"{marker} {line_num}: {ctx_line}")

                if len(results) > 500:  # Limit results
                    results.append("\n[Results truncated at 500 matches]")
                    break
            if len(results) > 500:
                break

        if results:
            return ToolResult(content="\n".join(results)[:MAX_OUTPUT_CHARS])
        return ToolResult(content="No matches found")
