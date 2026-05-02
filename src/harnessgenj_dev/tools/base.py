"""Base tool class for HGJ-dev tools."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolResult:
    """Result from a tool execution."""

    success: bool = True
    content: str = ""
    error: str = ""
    metadata: dict[str, Any] | None = None


class BaseTool(ABC):
    """Base class for all tools."""

    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = {}
    read_only: bool = False  # 是否只读工具（可并行执行）

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with given parameters."""

    def schema(self) -> dict[str, Any]:
        """Return the unified tool schema for LLM use.

        Returns: {"name": "...", "description": "...", "parameters": {...}}

        All providers convert this format internally:
        - OpenAI wraps it in {"type": "function", "function": {...}}
        - Anthropic converts it to {"name": ..., "input_schema": {...}}
        """
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }
