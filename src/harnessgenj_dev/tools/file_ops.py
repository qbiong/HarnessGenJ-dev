"""File operation tools - read, write, edit, list."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import BaseTool, ToolResult


class ReadFileTool(BaseTool):
    """Read a file's contents."""

    name = "read_file"
    description = "Read the contents of a file"
    read_only = True  # 只读工具，可并行执行
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path"},
            "line_start": {"type": "integer", "description": "Starting line (1-indexed)"},
            "line_end": {"type": "integer", "description": "Ending line (inclusive)"},
        },
        "required": ["path"],
    }

    async def execute(
        self,
        path: str,
        line_start: int | None = None,
        line_end: int | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        file_path = Path(path)
        if not file_path.exists():
            return ToolResult(success=False, error=f"File not found: {path}")
        content = file_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        if line_start is not None or line_end is not None:
            start = (line_start or 1) - 1
            end = line_end or len(lines)
            lines = lines[start:end]
        return ToolResult(content="\n".join(lines))


class WriteFileTool(BaseTool):
    """Write content to a file."""

    name = "write_file"
    description = "Write content to a file"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path"},
            "content": {"type": "string", "description": "Content to write"},
            "mode": {"type": "string", "enum": ["overwrite", "append"], "default": "overwrite"},
        },
        "required": ["path", "content"],
    }

    async def execute(self, path: str, content: str, mode: str = "overwrite", **kwargs: Any) -> ToolResult:
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        write_mode = "a" if mode == "append" else "w"
        with open(file_path, write_mode, encoding="utf-8") as f:
            f.write(content)
        return ToolResult(content=f"Written to {path}")


class EditFileTool(BaseTool):
    """Precisely edit text in a file by replacing old_string with new_string."""

    name = "edit_file"
    description = "Replace exact text in a file with new content"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path"},
            "old_string": {"type": "string", "description": "Text to find and replace"},
            "new_string": {"type": "string", "description": "Replacement text"},
            "replace_all": {"type": "boolean", "description": "Replace all occurrences", "default": False},
        },
        "required": ["path", "old_string", "new_string"],
    }

    async def execute(
        self,
        path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
        **kwargs: Any,
    ) -> ToolResult:
        file_path = Path(path)
        if not file_path.exists():
            return ToolResult(success=False, error=f"File not found: {path}")

        content = file_path.read_text(encoding="utf-8")
        count = content.count(old_string)

        if count == 0:
            return ToolResult(success=False, error=f"Text not found in {path}")

        if count > 1 and not replace_all:
            return ToolResult(
                success=False,
                error=(
                    f"Found {count} occurrences of the text. "
                    "Use replace_all=True to replace all, or make old_string more specific."
                ),
                metadata={"occurrences": count},
            )

        new_content = content.replace(old_string, new_string)
        file_path.write_text(new_content, encoding="utf-8")

        # Generate preview (lines around the edit)
        preview_lines = 3
        lines = new_content.splitlines()
        edit_char_idx = new_content.find(new_string)
        edit_line = new_content[:edit_char_idx].count("\n") if edit_char_idx >= 0 else 0
        start_line = max(0, edit_line - preview_lines)
        end_line = min(len(lines), edit_line + preview_lines + new_string.count("\n") + 1)
        preview = "\n".join(lines[start_line:end_line])

        return ToolResult(
            content=f"Replaced {count} occurrence(s) in {path}",
            metadata={
                "occurrences_replaced": count,
                "line": edit_line + 1,
                "preview": preview,
            },
        )


class ListDirectoryTool(BaseTool):
    """List directory contents."""

    name = "list_directory"
    description = "List files in a directory"
    read_only = True  # 只读工具，可并行执行
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Directory path"},
            "max_depth": {"type": "integer", "default": 1},
        },
        "required": ["path"],
    }

    async def execute(self, path: str, max_depth: int = 1, **kwargs: Any) -> ToolResult:
        dir_path = Path(path)
        if not dir_path.is_dir():
            return ToolResult(success=False, error=f"Not a directory: {path}")
        items = []
        for item in dir_path.iterdir():
            prefix = "D " if item.is_dir() else "F "
            items.append(f"{prefix}{item.name}")
        return ToolResult(content="\n".join(items))
