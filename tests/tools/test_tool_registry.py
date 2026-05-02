"""Tests for tool registry."""

import pytest

from harnessgenj_dev.tools.registry import (
    auto_register,
    execute_tool,
    get_execution_log,
    get_schemas,
    get_tool,
    get_tool_list,
    register,
    reset_registry,
)
from harnessgenj_dev.tools.base import BaseTool, ToolResult


class TestToolRegistry:
    """Test tool registration and lookup."""

    def test_auto_register_discovers_tools(self):
        """Auto-register should find tools."""
        reset_registry()
        registered = auto_register()
        assert len(registered) > 0

    def test_get_tool_list(self):
        """Should return list of tool names and descriptions."""
        auto_register()
        tools = get_tool_list()
        assert len(tools) > 0
        for t in tools:
            assert "name" in t
            assert "description" in t

    def test_get_schemas(self):
        """Should return schemas for LLM in unified format."""
        auto_register()
        schemas = get_schemas()
        assert len(schemas) > 0
        for schema in schemas:
            assert "name" in schema
            assert "description" in schema
            assert "parameters" in schema

    def test_get_tool_existing(self):
        """Should return tool instance for registered tool."""
        auto_register()
        tools = get_tool_list()
        if tools:
            tool = get_tool(tools[0]["name"])
            assert tool is not None

    def test_get_tool_nonexistent(self):
        """Should return None for unregistered tool."""
        tool = get_tool("nonexistent_tool_xyz")
        assert tool is None

    def test_reset_registry(self):
        """Reset should clear all registrations."""
        reset_registry()
        tools = get_tool_list()
        assert len(tools) == 0

    def test_get_execution_log_empty(self):
        """Log should be empty after reset."""
        reset_registry()
        log = get_execution_log()
        assert log == []


class TestExecuteTool:
    """Test tool execution through registry."""

    def test_execute_unregistered_tool(self):
        """Executing unregistered tool returns failure."""
        reset_registry()
        result = asyncio.get_event_loop().run_until_complete(
            execute_tool("nonexistent_xyz")
        )
        assert not result.success
        assert "Unknown tool" in result.error

    def test_execute_registered_tool(self):
        """Executing registered tool returns result."""
        auto_register()
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            execute_tool("read_file", path="/dev/null")
        )
        # Should not crash, may fail on actual execution but returns ToolResult
        assert result is not None
        assert isinstance(result, ToolResult)

import asyncio
