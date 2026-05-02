"""Plugin base class for HarnessGenJ-dev.

Defines the Plugin abstract base class and PluginInfo data structure
for building extendable plugins.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PluginLifecycle(str, Enum):
    """Plugin lifecycle stages."""

    INIT = "init"
    START = "start"
    STOP = "stop"
    SHUTDOWN = "shutdown"


@dataclass
class PluginInfo:
    """Metadata about a plugin."""

    name: str
    version: str = "0.1.0"
    description: str = ""
    author: str = ""
    min_hgj_dev_version: str = "0.1.0"
    dependencies: list[str] = field(default_factory=list)


class Plugin(ABC):
    """Base class for all HarnessGenJ-dev plugins.

    Plugins extend this class to add custom functionality to the system.
    They are managed by the PluginManager and receive lifecycle events.
    """

    info = PluginInfo(name="unknown")

    @abstractmethod
    async def initialize(self, config: dict[str, Any] | None = None) -> None:
        """Initialize the plugin with its configuration.

        Called once when the plugin is first loaded.

        Args:
            config: Optional plugin-specific configuration dict.
        """

    @abstractmethod
    async def shutdown(self) -> None:
        """Clean up resources used by the plugin.

        Called when the application is shutting down.
        """

    async def on_event(self, event_name: str, data: dict[str, Any] | None = None) -> None:
        """Handle a custom plugin event.

        Override this method to handle application-specific events.

        Args:
            event_name: Name of the event.
            data: Optional event data.
        """

    def get_commands(self) -> dict[str, Any]:
        """Return CLI commands provided by this plugin.

        Returns:
            Dict mapping command names to handler functions.
        """
        return {}

    def get_tools(self) -> list[type]:
        """Return tool classes provided by this plugin.

        Returns:
            List of BaseTool subclasses.
        """
        return []

    def get_hooks(self) -> dict[str, Any]:
        """Return hook handlers provided by this plugin.

        Returns:
            Dict mapping hook names to handler functions.
        """
        return {}
