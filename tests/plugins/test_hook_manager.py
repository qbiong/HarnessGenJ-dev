"""Tests for plugin hook manager."""

import asyncio

import pytest

from harnessgenj_dev.plugins.hook_manager import HookManager


class TestHookManager:
    """Test HookManager functionality."""

    def test_create_manager(self):
        manager = HookManager()
        assert manager is not None
        assert manager.hook_names == []

    def test_register_sync_hook(self):
        manager = HookManager()
        manager.register("test_hook", lambda: "ok")
        assert "test_hook" in manager.hook_names

    def test_register_async_hook(self):
        manager = HookManager()
        async def handler():
            return "async_ok"
        manager.register("test_hook", handler, is_async=True)
        assert "test_hook" in manager.hook_names

    def test_unregister_hook(self):
        manager = HookManager()
        handler = lambda: "ok"
        manager.register("test_hook", handler)
        manager.unregister("test_hook", handler)
        assert not manager.has_hooks("test_hook")

    def test_clear_single_hook(self):
        manager = HookManager()
        manager.register("hook_a", lambda: "a")
        manager.register("hook_b", lambda: "b")
        manager.clear("hook_a")
        assert not manager.has_hooks("hook_a")
        assert manager.has_hooks("hook_b")

    def test_clear_all_hooks(self):
        manager = HookManager()
        manager.register("hook_a", lambda: "a")
        manager.register("hook_b", lambda: "b")
        manager.clear()
        assert not manager.has_hooks("hook_a")
        assert not manager.has_hooks("hook_b")

    def test_has_hooks_empty(self):
        manager = HookManager()
        assert not manager.has_hooks("nonexistent")

    def test_has_hooks_with_handler(self):
        manager = HookManager()
        manager.register("test", lambda: True)
        assert manager.has_hooks("test")

    def test_multiple_handlers_same_hook(self):
        manager = HookManager()
        manager.register("test", lambda x: x + 1)
        manager.register("test", lambda x: x * 2)
        assert manager.has_hooks("test")

    def test_get_hooks_for_name(self):
        manager = HookManager()
        manager.register("test", lambda: "sync")
        async def async_handler():
            return "async"
        manager.register("test", async_handler, is_async=True)
        handlers = manager.get_hooks("test")
        assert len(handlers) == 2


@pytest.mark.asyncio
class TestHookManagerAsync:
    """Test HookManager async fire behavior."""

    async def test_fire_sync_hook(self):
        manager = HookManager()
        manager.register("test", lambda x: x * 2)
        results = await manager.fire("test", x=5)
        assert 10 in results

    async def test_fire_async_hook(self):
        manager = HookManager()
        async def double(x):
            return x * 3
        manager.register("test", double, is_async=True)
        results = await manager.fire("test", x=5)
        assert 15 in results

    async def test_fire_multiple_hooks(self):
        manager = HookManager()
        manager.register("test", lambda: "a")
        manager.register("test", lambda: "b")
        results = await manager.fire("test")
        assert "a" in results
        assert "b" in results

    async def test_fire_no_hooks(self):
        manager = HookManager()
        results = await manager.fire("nonexistent")
        assert results == []

    async def test_fire_with_error_recovery(self):
        """Error in one handler should not prevent others from running."""
        manager = HookManager()
        manager.register("test", lambda: 1 / 0)  # This will error
        manager.register("test", lambda: "ok")  # This should still run
        results = await manager.fire("test")
        assert "ok" in results

    async def test_fire_async_with_error_recovery(self):
        """Error in async handler should not prevent others from running."""
        manager = HookManager()
        async def failing():
            raise ValueError("test error")
        async def succeeding():
            return "ok"
        manager.register("test", failing, is_async=True)
        manager.register("test", succeeding, is_async=True)
        results = await manager.fire("test")
        assert "ok" in results

    async def test_fire_hooks_in_order(self):
        """Sync handlers should be called in registration order."""
        manager = HookManager()
        order = []
        manager.register("test", lambda: order.append(1))
        manager.register("test", lambda: order.append(2))
        manager.register("test", lambda: order.append(3))
        await manager.fire("test")
        assert order == [1, 2, 3]

    async def test_fire_with_kwargs(self):
        """Handlers should receive kwargs."""
        manager = HookManager()
        manager.register("test", lambda name, value: f"{name}={value}")
        results = await manager.fire("test", name="key", value=42)
        assert "key=42" in results
