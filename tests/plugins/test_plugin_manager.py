"""Tests for plugin manager."""

import asyncio

import pytest

from harnessgenj_dev.plugins.base import Plugin, PluginInfo
from harnessgenj_dev.plugins.manager import BUILTIN_HOOKS, PluginManager


class SamplePlugin(Plugin):
    """Sample plugin implementation."""

    info = PluginInfo(name="test", version="1.0.0")

    def __init__(self) -> None:
        self.init_called = False
        self.shutdown_called = False

    async def initialize(self, config=None) -> None:
        self.init_called = True

    async def shutdown(self) -> None:
        self.shutdown_called = True


class TestPluginManager:
    """Test PluginManager functionality."""

    def test_create_manager(self):
        manager = PluginManager()
        assert manager is not None
        assert not manager.is_initialized
        assert manager.plugin_count == 0

    def test_register_plugin(self):
        manager = PluginManager()
        manager.register(SamplePlugin())
        assert manager.plugin_count == 1
        assert "test" in manager.plugin_names

    def test_unregister_plugin(self):
        manager = PluginManager()
        plugin = SamplePlugin()
        manager.register(plugin)
        manager.unregister("test")
        assert manager.plugin_count == 0

    def test_unregister_nonexistent(self):
        manager = PluginManager()
        manager.unregister("nonexistent")  # Should not raise
        assert manager.plugin_count == 0

    def test_get_all_commands(self):
        manager = PluginManager()
        manager.register(SamplePlugin())
        commands = manager.get_all_commands()
        assert commands == {}

    def test_get_all_tools(self):
        manager = PluginManager()
        manager.register(SamplePlugin())
        tools = manager.get_all_tools()
        assert tools == []

    def test_get_command_not_found(self):
        manager = PluginManager()
        cmd = manager.get_command("nonexistent")
        assert cmd is None


@pytest.mark.asyncio
class TestPluginManagerLifecycle:
    """Test PluginManager lifecycle management."""

    async def test_initialize_all(self):
        manager = PluginManager()
        manager.register(SamplePlugin())
        await manager.initialize_all()
        assert manager.is_initialized
        # Find the plugin and check it was initialized
        plugin = manager.registry.get("test")
        assert plugin is not None
        assert plugin.init_called

    async def test_initialize_all_with_config(self):
        manager = PluginManager()
        manager.register(SamplePlugin())
        await manager.initialize_all(configs={"test": {"key": "value"}})
        assert manager.is_initialized

    async def test_shutdown_all(self):
        manager = PluginManager()
        plugin = SamplePlugin()
        manager.register(plugin)
        await manager.initialize_all()
        await manager.shutdown_all()
        assert not manager.is_initialized
        assert plugin.shutdown_called

    async def test_fire_hook_app_startup(self):
        manager = PluginManager()
        results = await manager.fire_hook("app_startup")
        assert results == []

    async def test_fire_hook_with_handlers(self):
        manager = PluginManager()
        manager.hooks.register("custom", lambda x: x * 2)
        results = await manager.fire_hook("custom", x=5)
        assert 10 in results

    async def test_plugin_with_commands(self):
        class CommandPlugin(Plugin):
            info = PluginInfo(name="cmd", version="1.0.0")
            async def initialize(self, config=None): pass
            async def shutdown(self): pass
            def get_commands(self):
                return {"hello": lambda: "world"}

        manager = PluginManager()
        manager.register(CommandPlugin())
        commands = manager.get_all_commands()
        assert "hello" in commands

    async def test_plugin_with_tools(self):
        from harnessgenj_dev.tools.base import BaseTool, ToolResult

        class CustomTool(BaseTool):
            name = "custom_tool"
            description = "A custom tool"
            async def execute(self, **kwargs):
                return ToolResult(success=True, content="done")

        class ToolPlugin(Plugin):
            info = PluginInfo(name="tool", version="1.0.0")
            async def initialize(self, config=None): pass
            async def shutdown(self): pass
            def get_tools(self):
                return [CustomTool]

        manager = PluginManager()
        manager.register(ToolPlugin())
        tools = manager.get_all_tools()
        assert len(tools) == 1
        assert tools[0].name == "custom_tool"

    async def test_plugin_with_hooks(self):
        class HookPlugin(Plugin):
            info = PluginInfo(name="hook", version="1.0.0")
            async def initialize(self, config=None): pass
            async def shutdown(self): pass
            def get_hooks(self):
                return {"before_tool_call": lambda: "hooked"}

        manager = PluginManager()
        manager.register(HookPlugin())
        await manager.initialize_all()
        results = await manager.fire_hook("before_tool_call")
        assert "hooked" in results


class TestBuiltinHooks:
    """Test built-in hook definitions."""

    def test_builtin_hooks_list(self):
        assert isinstance(BUILTIN_HOOKS, list)
        assert len(BUILTIN_HOOKS) > 0

    def test_app_startup_hook(self):
        assert "app_startup" in BUILTIN_HOOKS

    def test_app_shutdown_hook(self):
        assert "app_shutdown" in BUILTIN_HOOKS

    def test_before_tool_call_hook(self):
        assert "before_tool_call" in BUILTIN_HOOKS

    def test_after_tool_call_hook(self):
        assert "after_tool_call" in BUILTIN_HOOKS
