"""Hook manager for plugin lifecycle and event system."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class HookManager:
    """Manages hook registration and execution for plugins.

    Hooks are named callbacks that plugins can register to participate
    in application lifecycle events and custom events.

    Usage:
        hooks = HookManager()
        hooks.register("before_tool_call", my_handler)
        await hooks.fire("before_tool_call", tool_name="read_file")
    """

    def __init__(self) -> None:
        self._hooks: dict[str, list[Callable]] = {}
        self._async_hooks: dict[str, list[Callable]] = {}

    def register(self, hook_name: str, handler: Callable, is_async: bool = False) -> None:
        """Register a hook handler.

        Args:
            hook_name: Name of the hook (e.g., "before_tool_call").
            handler: Callable handler function.
            is_async: If True, handler is an async function.
        """
        if is_async:
            self._async_hooks.setdefault(hook_name, []).append(handler)
        else:
            self._hooks.setdefault(hook_name, []).append(handler)

    def unregister(self, hook_name: str, handler: Callable) -> None:
        """Unregister a specific hook handler.

        Args:
            hook_name: Name of the hook.
            handler: The handler to remove.
        """
        if hook_name in self._hooks:
            self._hooks[hook_name].remove(handler)
        if hook_name in self._async_hooks:
            self._async_hooks[hook_name].remove(handler)

    def clear(self, hook_name: str | None = None) -> None:
        """Clear hook handlers.

        Args:
            hook_name: If given, clear only this hook. Otherwise clear all.
        """
        if hook_name:
            self._hooks.pop(hook_name, None)
            self._async_hooks.pop(hook_name, None)
        else:
            self._hooks.clear()
            self._async_hooks.clear()

    async def fire(self, hook_name: str, **kwargs: Any) -> list[Any]:
        """Fire a hook, calling all registered handlers.

        Handlers are called in registration order. Results are collected
        and returned as a list.

        Args:
            hook_name: Name of the hook to fire.
            **kwargs: Arguments passed to each handler.

        Returns:
            List of results from all handlers.
        """
        results: list[Any] = []
        handlers = self._hooks.get(hook_name, [])
        async_handlers = self._async_hooks.get(hook_name, [])

        # Call sync handlers
        for handler in handlers:
            try:
                result = handler(**kwargs)
                results.append(result)
            except Exception as exc:
                logger.warning("Hook %s handler failed: %s", hook_name, exc)

        # Call async handlers in parallel
        if async_handlers:
            tasks = []
            for handler in async_handlers:
                try:
                    task = asyncio.create_task(handler(**kwargs))
                    tasks.append(task)
                except Exception as exc:
                    logger.warning("Hook %s async handler creation failed: %s", hook_name, exc)

            for task in asyncio.as_completed(tasks):
                try:
                    result = await task
                    results.append(result)
                except Exception as exc:
                    logger.warning("Hook %s async handler failed: %s", hook_name, exc)

        return results

    def get_hooks(self, hook_name: str | None = None) -> list[str]:
        """Get registered hook names.

        Args:
            hook_name: If given, return handler count for this hook.

        Returns:
            If hook_name is given, list of handler names. Otherwise list of all hook names.
        """
        if hook_name:
            sync = self._hooks.get(hook_name, [])
            async_h = self._async_hooks.get(hook_name, [])
            return [f"sync_{i}" for i in range(len(sync))] + [f"async_{i}" for i in range(len(async_h))]
        return list(set(list(self._hooks.keys()) + list(self._async_hooks.keys())))

    def has_hooks(self, hook_name: str) -> bool:
        """Check if any handlers are registered for a hook."""
        return bool(self._hooks.get(hook_name) or self._async_hooks.get(hook_name))

    @property
    def hook_names(self) -> list[str]:
        """All registered hook names."""
        return list(set(list(self._hooks.keys()) + list(self._async_hooks.keys())))
