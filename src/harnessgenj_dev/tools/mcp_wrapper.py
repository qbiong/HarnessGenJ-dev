"""MCP tool integration - expose MCP tools as HGJ tools."""

from __future__ import annotations

import logging
from typing import Any

from .base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class MCPToolWrapper(BaseTool):
    """Wrapper to expose MCP tools as HGJ tools.

    This allows MCP server tools to be used within the Agent's ReAct loop.
    """

    def __init__(self, mcp_manager, server_name: str, tool_name: str) -> None:
        self._mcp_manager = mcp_manager
        self._server_name = server_name
        self._tool_name = tool_name
        self.name = f"mcp_{server_name}_{tool_name}"
        self.description = f"MCP tool: {tool_name} (from {server_name})"
        self.read_only = True  # Assume read-only, can be overridden

    @property
    def mcp_tool_name(self) -> str:
        return self._tool_name

    @property
    def server_name(self) -> str:
        return self._server_name

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the MCP tool via the client manager."""
        try:
            result = await self._mcp_manager.call_tool(self._server_name, self._tool_name, kwargs)
            if result.get("success"):
                return ToolResult(content=result.get("content", ""))
            else:
                return ToolResult(success=False, error=result.get("error", "Unknown error"))
        except Exception as e:
            logger.exception(f"MCP tool execution failed: {self._tool_name}")
            return ToolResult(success=False, error=str(e))


def register_mcp_tools(mcp_manager) -> list[str]:
    """Register all MCP tools as HGJ tools.

    Args:
        mcp_manager: MCPClientManager instance with connected servers.

    Returns:
        List of registered tool names.
    """
    from .registry import _registry

    registered = []
    all_tools = mcp_manager.list_all_tools()

    for mcp_tool in all_tools:
        tool = MCPToolWrapper(mcp_manager, mcp_tool.server_name, mcp_tool.name)

        # Generate parameters from input schema
        tool.parameters = mcp_tool.input_schema
        tool.description = mcp_tool.description

        registry_name = tool.name
        _registry[registry_name] = tool
        registered.append(registry_name)
        logger.debug(f"Registered MCP tool: {registry_name}")

    return registered


def create_mcp_tool_class(mcp_manager, server_name: str, tool_name: str, description: str):
    """Dynamically create an MCP tool class.

    This can be used for more complex tool registration scenarios.
    """

    class DynamicMCPTool(BaseTool):
        name = f"mcp_{server_name}_{tool_name}"
        description = description
        read_only = True

        def __init__(self) -> None:
            super().__init__()
            self._mcp_manager = mcp_manager
            self._server_name = server_name
            self._tool_name = tool_name

        async def execute(self, **kwargs: Any) -> ToolResult:
            try:
                result = await self._mcp_manager.call_tool(self._server_name, self._tool_name, kwargs)
                if result.get("success"):
                    return ToolResult(content=result.get("content", ""))
                else:
                    return ToolResult(success=False, error=result.get("error", ""))
            except Exception as e:
                return ToolResult(success=False, error=str(e))

    return DynamicMCPTool
