"""HGJ Plugin System.

Plugins extend HGJ-dev with custom tools, roles, and workflows.

Usage:
    from harnessgenj_dev.plugins import PluginManager, Plugin, PluginInfo

    class MyPlugin(Plugin):
        info = PluginInfo(name="my-plugin", version="1.0.0", description="My custom plugin")

        async def initialize(self, config=None):
            # Setup code
            pass

        async def shutdown(self):
            # Cleanup code
            pass
"""

from .base import Plugin, PluginInfo, PluginLifecycle
from .hook_manager import HookManager
from .manager import PluginManager
from .registry import PluginRegistry

__all__ = [
    "Plugin",
    "PluginInfo",
    "PluginLifecycle",
    "PluginRegistry",
    "HookManager",
    "PluginManager",
]

# Global hook manager instance for application-wide hooks
_hook_manager: HookManager | None = None


def get_hook_manager() -> HookManager:
    """Get the global hook manager instance."""
    global _hook_manager
    if _hook_manager is None:
        _hook_manager = HookManager()
    return _hook_manager
