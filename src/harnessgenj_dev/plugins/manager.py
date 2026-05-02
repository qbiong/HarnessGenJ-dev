"""Plugin manager - orchestrates plugin lifecycle, hooks, and events."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .base import Plugin
from .hook_manager import HookManager
from .registry import PluginRegistry

logger = logging.getLogger(__name__)

# Built-in hook points in the application lifecycle
BUILTIN_HOOKS = [
    "app_startup",       # Fired when the application starts
    "app_shutdown",      # Fired when the application shuts down
    "before_tool_call",  # Fired before a tool is executed
    "after_tool_call",   # Fired after a tool is executed
    "before_agent_run",  # Fired before the agent starts processing
    "after_agent_run",   # Fired after the agent finishes
    "user_message",      # Fired when a user message is received
    "agent_response",    # Fired when the agent produces a response
]


class PluginManager:
    """Central manager for all plugin-related operations.

    Combines PluginRegistry and HookManager to provide a unified API
    for plugin lifecycle management and event handling.

    Usage:
        manager = PluginManager()
        manager.register(MyPlugin())
        await manager.initialize_all(config={"my-plugin": {"key": "value"}})

        # Fire hooks
        await manager.fire_hook("before_tool_call", tool_name="read_file")

        # Get commands/tools from plugins
        commands = manager.get_all_commands()
        tools = manager.get_all_tools()
    """

    def __init__(self, plugin_dir: Path | str | None = None) -> None:
        """Initialize the plugin manager.

        Args:
            plugin_dir: Optional directory to scan for external plugins.
        """
        self.registry = PluginRegistry()
        self.hooks = HookManager()
        self._plugin_dir = Path(plugin_dir) if plugin_dir else None
        self._is_initialized = False

    def register(self, plugin: Plugin) -> None:
        """Register a plugin instance.

        Args:
            plugin: Initialized plugin instance.
        """
        self.registry.register(plugin)
        logger.info("Plugin registered: %s", plugin.info.name)

    def unregister(self, name: str) -> None:
        """Unregister a plugin by name.

        Args:
            name: Plugin name.
        """
        plugin = self.registry.get(name)
        if plugin:
            self.registry.unregister(name)
            logger.info("Plugin unregistered: %s", name)

    async def initialize_all(
        self, configs: dict[str, dict[str, Any]] | None = None
    ) -> None:
        """Initialize all registered plugins.

        Args:
            configs: Optional dict mapping plugin names to their configs.
        """
        configs = configs or {}
        for name, plugin in self.registry.plugins.items():
            plugin_config = configs.get(name)
            await self.registry.initialize_plugin(plugin, plugin_config)

        # Register plugin-provided hooks
        for name, plugin in self.registry.plugins.items():
            for hook_name, handler in plugin.get_hooks().items():
                is_async = asyncio.iscoroutinefunction(handler)
                self.hooks.register(hook_name, handler, is_async=is_async)

        self._is_initialized = True
        logger.info("All plugins initialized (%d total)", len(self.registry.plugins))

    async def shutdown_all(self) -> None:
        """Shutdown all registered plugins."""
        # Fire shutdown hook
        await self.fire_hook("app_shutdown")

        # Clear hooks
        self.hooks.clear()

        # Shutdown plugins
        await self.registry.shutdown_all()
        self._is_initialized = False

    async def fire_hook(self, hook_name: str, **kwargs: Any) -> list[Any]:
        """Fire a named hook, calling all registered handlers.

        Args:
            hook_name: Name of the hook.
            **kwargs: Arguments passed to handlers.

        Returns:
            List of handler results.
        """
        return await self.hooks.fire(hook_name, **kwargs)

    def get_command(self, name: str) -> Callable | None:
        """Get a CLI command from any plugin.

        Args:
            name: Command name.

        Returns:
            Command handler or None.
        """
        for plugin in self.registry.plugins.values():
            commands = plugin.get_commands()
            if name in commands:
                return commands[name]
        return None

    def get_all_commands(self) -> dict[str, Callable]:
        """Get all CLI commands from all plugins.

        Returns:
            Dict mapping command names to handlers.
        """
        all_commands: dict[str, Callable] = {}
        for plugin in self.registry.plugins.values():
            all_commands.update(plugin.get_commands())
        return all_commands

    def get_all_tools(self) -> list[type]:
        """Get all tool classes from all plugins.

        Returns:
            List of BaseTool subclasses.
        """
        all_tools: list[type] = []
        for plugin in self.registry.plugins.values():
            all_tools.extend(plugin.get_tools())
        return all_tools

    @property
    def is_initialized(self) -> bool:
        """Whether all plugins have been initialized."""
        return self._is_initialized

    @property
    def plugin_count(self) -> int:
        """Number of registered plugins."""
        return len(self.registry.plugins)

    @property
    def plugin_names(self) -> list[str]:
        """Names of all registered plugins."""
        return list(self.registry.plugins.keys())

    @property
    def hook_names(self) -> list[str]:
        """All registered hook names."""
        return self.hooks.hook_names
