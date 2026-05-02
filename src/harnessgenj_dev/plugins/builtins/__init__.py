"""Built-in plugins for HarnessGenJ-dev.

This package provides ready-to-use plugins that ship with HGJ-dev.
"""

from .github_plugin import GitHubPlugin

__all__ = ["GitHubPlugin"]


def register_builtin_plugins(registry) -> None:
    """Register all built-in plugins with the given registry.

    Args:
        registry: A PluginRegistry instance.
    """
    from .github_plugin import GitHubPlugin

    registry.register(GitHubPlugin())
