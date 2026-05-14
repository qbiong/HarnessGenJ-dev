"""Tool registry - register and dispatch tools."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .base import BaseTool, ToolResult

_registry: dict[str, BaseTool] = {}
_execution_log: list[dict[str, Any]] = []


@dataclass
class ToolLogEntry:
    """Record of a tool execution."""

    tool_name: str
    args: dict[str, Any]
    result: ToolResult
    timestamp: float = field(default_factory=time.time)


def register(name: str) -> Any:
    """Decorator to register a tool class."""

    def decorator(cls: type[BaseTool]) -> type[BaseTool]:
        _registry[name] = cls()
        return cls

    return decorator


def auto_register(package_path: str | None = None) -> list[str]:
    """Auto-discover and register all tools in the tools package.

    Scans the tools directory for *_ops.py and base.py files,
    imports them, and registers all BaseTool subclasses.

    Args:
        package_path: Optional explicit package path. If None, uses
            the tools package relative to this module.

    Returns:
        List of registered tool names.
    """
    if package_path is None:
        package_path = str(Path(__file__).parent)

    registered = []
    tools_dir = Path(package_path)

    for file_path in tools_dir.glob("*_ops.py"):
        module_name = file_path.stem
        try:
            # Import the module to trigger any decorator-based registration
            import importlib

            mod = importlib.import_module(f".{module_name}", package="harnessgenj_dev.tools")

            # Find all BaseTool subclasses and register them
            for attr_name in dir(mod):
                attr = getattr(mod, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BaseTool)
                    and attr is not BaseTool
                    and hasattr(attr, "name")
                    and attr.name
                ):
                    if attr.name not in _registry:
                        _registry[attr.name] = attr()
                        registered.append(attr.name)
        except Exception as e:
            # Log but don't fail on import errors
            from ..utils.logger import get_logger

            get_logger("tool_registry").warning("Failed to import tool module %s: %s", module_name, e)

    return registered


def get_tool(name: str) -> BaseTool | None:
    """Get a registered tool by name."""
    return _registry.get(name)


def get_schemas() -> list[dict[str, Any]]:
    """Get all tool schemas for LLM."""
    return [tool.schema() for tool in _registry.values()]


def get_tool_list() -> list[dict[str, str]]:
    """Get list of all registered tools with name and description."""
    return [{"name": tool.name, "description": tool.description} for tool in _registry.values()]


def get_execution_log(limit: int = 50) -> list[dict[str, Any]]:
    """Get recent tool execution log entries.

    Args:
        limit: Maximum number of entries to return (most recent first).

    Returns:
        List of log entries.
    """
    recent = _execution_log[-limit:]
    recent.reverse()
    return recent


async def execute_tool(name: str, **kwargs: Any) -> ToolResult:
    """Execute a tool by name with logging."""
    tool = get_tool(name)
    if tool is None:
        return ToolResult(success=False, error=f"Unknown tool: {name}")

    # Path whitelist: ensure file ops stay within project boundary (Claude Code isolation pattern)
    path_keys = {"path", "cwd", "file_path"}
    if name in ("read_file", "write_file", "edit_file", "list_directory") and any(k in kwargs for k in path_keys):
        for pk in path_keys:
            if pk in kwargs and kwargs[pk]:
                import os
                target = os.path.abspath(str(kwargs[pk]))
                # Get active project path
                project_root = None
                try:
                    from harnessgenj_dev.projects import get_active_project
                    active = get_active_project()
                    if active:
                        project_root = os.path.abspath(active["path"])
                except Exception:
                    pass
                if project_root:
                    project_root = os.path.normpath(os.path.abspath(str(project_root)))
                    target = os.path.normpath(target)
                    if not target.startswith(project_root):
                        return ToolResult(
                            success=False,
                            error=f"Path '{target}' is outside project boundary '{project_root}'. "
                                  f"Operate only within the user's project directory.",
                        )

    try:
        result = await tool.execute(**kwargs)
        # Log the execution
        _execution_log.append(
            {
                "tool_name": name,
                "args": {k: str(v)[:100] for k, v in kwargs.items()},
                "success": result.success,
                "timestamp": time.time(),
            }
        )
        return result
    except Exception as e:
        error_result = ToolResult(success=False, error=str(e))
        _execution_log.append(
            {
                "tool_name": name,
                "args": {k: str(v)[:100] for k, v in kwargs.items()},
                "success": False,
                "timestamp": time.time(),
            }
        )
        return error_result


async def execute_tools_parallel(tool_calls: list[dict[str, Any]]) -> list[ToolResult]:
    """Execute multiple tool calls with parallel execution for read-only tools.

    Claude Code 规则：
    - 只读工具（read_file, search_code, list_directory）并行执行
    - 写操作工具（write_file, edit_file, run_command）顺序执行

    Args:
        tool_calls: [{"name": "tool_name", "input": {...}}, ...]

    Returns:
        List of ToolResult in the same order as tool_calls
    """
    if not tool_calls:
        return []

    # 分类工具：只读 vs 写操作
    read_only_calls = []
    write_calls = []

    for i, tc in enumerate(tool_calls):
        tool_name = tc.get("name", "")
        tool = get_tool(tool_name)
        if tool and getattr(tool, "read_only", False):
            read_only_calls.append((i, tc))
        else:
            write_calls.append((i, tc))

    results: list[ToolResult] = [ToolResult()] * len(tool_calls)

    # 并行执行只读工具
    if read_only_calls:
        parallel_tasks = []
        for idx, tc in read_only_calls:
            task = execute_tool(tc.get("name", ""), **tc.get("input", {}))
            parallel_tasks.append((idx, task))

        # 使用 asyncio.gather 并行执行
        import asyncio

        task_results = await asyncio.gather(*[t[1] for t in parallel_tasks], return_exceptions=True)

        for (idx, _), result in zip(parallel_tasks, task_results):
            if isinstance(result, Exception):
                results[idx] = ToolResult(success=False, error=str(result))
            else:
                results[idx] = result

    # 顺序执行写操作工具
    for idx, tc in write_calls:
        result = await execute_tool(tc.get("name", ""), **tc.get("input", {}))
        results[idx] = result

    return results


def reset_registry() -> None:
    """Clear all registered tools. Useful for testing."""
    _registry.clear()
    _execution_log.clear()
