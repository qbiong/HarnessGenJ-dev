"""Tests for plugin registry."""

import asyncio

import pytest

from harnessgenj_dev.plugins.base import Plugin, PluginInfo
from harnessgenj_dev.plugins.registry import PluginRegistry


class SimplePlugin(Plugin):
    """Simple plugin for testing."""

    info = PluginInfo(name="simple", version="0.1.0")

    def __init__(self) -> None:
        self.init_called = False
        self.shutdown_called = False

    async def initialize(self, config=None) -> None:
        self.init_called = True

    async def shutdown(self) -> None:
        self.shutdown_called = True


class TestPluginRegistry:
    """Test PluginRegistry functionality."""

    def test_create_registry(self):
        registry = PluginRegistry()
        assert registry is not None
        assert len(registry.plugins) == 0

    def test_register_plugin(self):
        registry = PluginRegistry()
        plugin = SimplePlugin()
        registry.register(plugin)
        assert registry.is_registered("simple")
        assert len(registry.plugins) == 1

    def test_unregister_plugin(self):
        registry = PluginRegistry()
        plugin = SimplePlugin()
        registry.register(plugin)
        result = registry.unregister("simple")
        assert result is plugin
        assert not registry.is_registered("simple")

    def test_unregister_nonexistent(self):
        registry = PluginRegistry()
        result = registry.unregister("missing")
        assert result is None

    def test_get_plugin(self):
        registry = PluginRegistry()
        plugin = SimplePlugin()
        registry.register(plugin)
        found = registry.get("simple")
        assert found is plugin

    def test_get_nonexistent_plugin(self):
        registry = PluginRegistry()
        found = registry.get("missing")
        assert found is None

    def test_list_plugins(self):
        registry = PluginRegistry()
        registry.register(SimplePlugin())
        infos = registry.list_plugins()
        assert len(infos) == 1
        assert infos[0].name == "simple"

    def test_is_registered(self):
        registry = PluginRegistry()
        assert not registry.is_registered("simple")
        registry.register(SimplePlugin())
        assert registry.is_registered("simple")

    def test_multiple_plugins(self):
        registry = PluginRegistry()
        registry.register(SimplePlugin())

        class AnotherPlugin(SimplePlugin):
            info = PluginInfo(name="another", version="0.2.0")

        registry.register(AnotherPlugin())
        assert registry.plugin_count == 2
        assert "simple" in registry.plugin_names
        assert "another" in registry.plugin_names


@pytest.mark.asyncio
class TestPluginRegistryLifecycle:
    """Test PluginRegistry lifecycle methods."""

    async def test_initialize_plugin(self):
        registry = PluginRegistry()
        plugin = SimplePlugin()
        registry.register(plugin)
        await registry.initialize_plugin(plugin)
        assert plugin.init_called

    async def test_initialize_plugin_with_config(self):
        registry = PluginRegistry()
        plugin = SimplePlugin()
        registry.register(plugin)
        await registry.initialize_plugin(plugin, {"key": "value"})
        assert plugin.init_called

    async def test_shutdown_plugin(self):
        registry = PluginRegistry()
        plugin = SimplePlugin()
        registry.register(plugin)
        await registry.initialize_plugin(plugin)
        await registry.shutdown_plugin(plugin)
        assert plugin.shutdown_called

    async def test_shutdown_all(self):
        registry = PluginRegistry()
        p1 = SimplePlugin()
        p1.info = PluginInfo(name="p1", version="0.1.0")
        registry.register(p1)

        p2 = SimplePlugin()
        p2.info = PluginInfo(name="p2", version="0.1.0")
        registry.register(p2)

        await registry.initialize_plugin(p1)
        await registry.initialize_plugin(p2)
        await registry.shutdown_all()

        assert p1.shutdown_called
        assert p2.shutdown_called
        assert len(registry.plugins) == 0

    async def test_initialize_plugin_error(self):
        """Error during init should be raised."""
        registry = PluginRegistry()

        class FailingPlugin(Plugin):
            info = PluginInfo(name="failing", version="0.1.0")
            async def initialize(self, config=None):
                raise RuntimeError("init failed")
            async def shutdown(self):
                pass

        plugin = FailingPlugin()
        registry.register(plugin)
        with pytest.raises(RuntimeError, match="init failed"):
            await registry.initialize_plugin(plugin)
