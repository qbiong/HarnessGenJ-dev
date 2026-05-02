"""MCP (Model Context Protocol) integration for HarnessGenJ-dev.

Reference: Real Python MCP Client tutorial + MCP Python SDK
- MCP Client: Connect to MCP servers via stdio/SSE
- MCP Tools: Expose MCP tools as HGJ tools
- MCP Resources: Expose MCP resources as context
"""

from __future__ import annotations

import logging
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Try to import MCP SDK
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    logger.warning("MCP SDK not installed. Run: pip install mcp")


@dataclass
class MCPTool:
    """MCP tool wrapper."""

    name: str
    description: str
    input_schema: dict[str, Any]
    server_name: str


@dataclass
class MCPResource:
    """MCP resource wrapper."""

    uri: str
    name: str
    description: str | None
    mime_type: str | None


@dataclass
class MCPServer:
    """MCP server connection."""

    name: str
    server_path: str
    client_session: ClientSession | None = None
    tools: list[MCPTool] = field(default_factory=list)
    resources: list[MCPResource] = field(default_factory=list)


class MCPClientManager:
    """Manage MCP server connections and tool discovery.

    Usage:
        mgr = MCPClientManager()
        await mgr.connect_server("my-server", "./server.py")
        tools = await mgr.list_tools("my-server")
        result = await mgr.call_tool("my-server", "tool_name", args)
    """

    def __init__(self) -> None:
        self._servers: dict[str, MCPServer] = {}
        self._exit_stack: AsyncExitStack | None = None

    async def connect_server(
        self,
        name: str,
        server_path: str,
        env: dict[str, str] | None = None,
    ) -> bool:
        """Connect to an MCP server via stdio transport.

        Args:
            name: Friendly name for this server.
            server_path: Path to the MCP server script.
            env: Optional environment variables.

        Returns:
            True if connected successfully.
        """
        if not MCP_AVAILABLE:
            logger.error("MCP SDK not available")
            return False

        try:
            server_params = StdioServerParameters(
                command="python",
                args=[str(server_path)],
                env=env,
            )

            read, write = await stdio_client(server_params)
            client_session = ClientSession(read, write)
            await client_session.initialize()

            # Discover tools and resources
            tools_result = await client_session.list_tools()
            tools = [
                MCPTool(
                    name=t.name,
                    description=t.description or "",
                    input_schema=t.inputSchema,
                    server_name=name,
                )
                for t in tools_result.tools
            ]

            resources_result = await client_session.list_resources()
            resources = [
                MCPResource(
                    uri=r.uri,
                    name=r.name,
                    description=r.description,
                    mime_type=r.mimeType,
                )
                for r in (resources_result.resources or [])
            ]

            self._servers[name] = MCPServer(
                name=name,
                server_path=server_path,
                client_session=client_session,
                tools=tools,
                resources=resources,
            )

            logger.info(f"Connected to MCP server '{name}' with {len(tools)} tools")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to MCP server '{name}': {e}")
            return False

    async def disconnect_server(self, name: str) -> bool:
        """Disconnect from an MCP server."""
        if name not in self._servers:
            return False

        server = self._servers[name]
        if server.client_session:
            await server.client_session.close()

        del self._servers[name]
        logger.info(f"Disconnected from MCP server '{name}'")
        return True

    def list_servers(self) -> list[str]:
        """List connected server names."""
        return list(self._servers.keys())

    def list_tools(self, server_name: str) -> list[MCPTool]:
        """List tools available on a server."""
        if server_name in self._servers:
            return self._servers[server_name].tools
        return []

    def list_all_tools(self) -> list[MCPTool]:
        """List tools from all connected servers."""
        all_tools = []
        for server in self._servers.values():
            all_tools.extend(server.tools)
        return all_tools

    def list_resources(self, server_name: str) -> list[MCPResource]:
        """List resources available on a server."""
        if server_name in self._servers:
            return self._servers[server_name].resources
        return []

    async def call_tool(
        self, server_name: str, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Call a tool on an MCP server.

        Args:
            server_name: Server to call the tool on.
            tool_name: Name of the tool to call.
            arguments: Tool arguments.

        Returns:
            Tool result dict with success/content/error keys.
        """
        if server_name not in self._servers:
            return {"success": False, "error": f"Server '{server_name}' not connected"}

        server = self._servers[server_name]
        if not server.client_session:
            return {"success": False, "error": "Server not initialized"}

        try:
            result = await server.client_session.call_tool(tool_name, arguments)
            # Extract content from result
            content_parts = []
            for content in (result.content or []):
                if hasattr(content, "text"):
                    content_parts.append(content.text)
                else:
                    content_parts.append(str(content))

            return {
                "success": True,
                "content": "\n".join(content_parts),
            }
        except Exception as e:
            logger.error(f"Tool call failed: {e}")
            return {"success": False, "error": str(e)}

    async def read_resource(self, server_name: str, uri: str) -> str | None:
        """Read a resource from an MCP server."""
        if server_name not in self._servers:
            return None

        server = self._servers[server_name]
        if not server.client_session:
            return None

        try:
            result = await server.client_session.read_resource(uri)
            if result.contents:
                for content in result.contents:
                    if hasattr(content, "text"):
                        return content.text
            return None
        except Exception as e:
            logger.error(f"Resource read failed: {e}")
            return None

    async def close_all(self) -> None:
        """Close all server connections."""
        for name in list(self._servers.keys()):
            await self.disconnect_server(name)


# Global MCP client manager
_mcp_manager: MCPClientManager | None = None


def get_mcp_manager() -> MCPClientManager:
    """Get the global MCP client manager."""
    global _mcp_manager
    if _mcp_manager is None:
        _mcp_manager = MCPClientManager()
    return _mcp_manager
