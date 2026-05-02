"""Plugin registry and discovery mechanism."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .base import Plugin, PluginInfo

logger = logging.getLogger(__name__)


class PluginRegistry:
    """Registry for discovering, loading, and managing plugins.

    Plugins can be loaded from:
    1. Built-in plugins in the plugins/builtin/ directory
    2. External plugins from a configured plugins/ directory
    3. Programmatically via register()
    """

    def __init__(self) -> None:
        self._plugins: dict[str, Plugin] = {}
        self._plugin_dirs: list[Path] = []

    def register(self, plugin: Plugin) -> None:
        """Register a plugin instance.

        Args:
            plugin: Initialized plugin instance.
        """
        self._plugins[plugin.info.name] = plugin

    def unregister(self, name: str) -> Plugin | None:
        """Unregister and return a plugin.

        Args:
            name: Plugin name.

        Returns:
            The unregistered plugin, or None if not found.
        """
        return self._plugins.pop(name, None)

    def get(self, name: str) -> Plugin | None:
        """Get a registered plugin by name.

        Args:
            name: Plugin name.

        Returns:
            Plugin instance or None.
        """
        return self._plugins.get(name)

    def list_plugins(self) -> list[PluginInfo]:
        """Get info for all registered plugins.

        Returns:
            List of PluginInfo objects.
        """
        return [p.info for p in self._plugins.values()]

    def is_registered(self, name: str) -> bool:
        """Check if a plugin is registered."""
        return name in self._plugins

    async def initialize_plugin(self, plugin: Plugin, config: dict[str, Any] | None = None) -> None:
        """Initialize a plugin with its configuration.

        Args:
            plugin: Plugin instance to initialize.
            config: Optional configuration dict.
        """
        try:
            await plugin.initialize(config)
            logger.info("Plugin initialized: %s v%s", plugin.info.name, plugin.info.version)
        except Exception as exc:
            logger.error("Plugin %s failed to initialize: %s", plugin.info.name, exc)
            raise

    async def shutdown_plugin(self, plugin: Plugin) -> None:
        """Shutdown a plugin.

        Args:
            plugin: Plugin instance to shutdown.
        """
        try:
            await plugin.shutdown()
            logger.info("Plugin shutdown: %s", plugin.info.name)
        except Exception as exc:
            logger.warning("Plugin %s shutdown error: %s", plugin.info.name, exc)

    async def shutdown_all(self) -> None:
        """Shutdown all registered plugins."""
        for name, plugin in list(self._plugins.items()):
            await self.shutdown_plugin(plugin)
        self._plugins.clear()

    @property
    def plugin_count(self) -> int:
        """Number of registered plugins."""
        return len(self._plugins)

    @property
    def plugin_names(self) -> list[str]:
        """Names of all registered plugins."""
        return list(self._plugins.keys())

    @property
    def plugins(self) -> dict[str, Plugin]:
        """All registered plugins."""
        return dict(self._plugins)
