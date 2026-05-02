"""Tests for plugin base class."""

import pytest

from harnessgenj_dev.plugins.base import Plugin, PluginInfo, PluginLifecycle


class DummyPlugin(Plugin):
    """Concrete plugin implementation for testing."""

    info = PluginInfo(
        name="test-plugin",
        version="1.0.0",
        description="A test plugin",
        author="test",
    )

    def __init__(self) -> None:
        self.initialized = False
        self.shutdown_called = False
        self.events: list[str] = []

    async def initialize(self, config=None) -> None:
        self.initialized = True

    async def shutdown(self) -> None:
        self.shutdown_called = True

    async def on_event(self, event_name, data=None) -> None:
        self.events.append(event_name)


class TestPluginInfo:
    """Test PluginInfo dataclass."""

    def test_default_values(self):
        info = PluginInfo(name="test")
        assert info.name == "test"
        assert info.version == "0.1.0"
        assert info.description == ""
        assert info.author == ""
        assert info.min_hgj_dev_version == "0.1.0"
        assert info.dependencies == []

    def test_custom_values(self):
        info = PluginInfo(
            name="my-plugin",
            version="2.0.0",
            description="My custom plugin",
            author="dev",
            min_hgj_dev_version="0.2.0",
            dependencies=["other-plugin"],
        )
        assert info.name == "my-plugin"
        assert info.version == "2.0.0"
        assert info.description == "My custom plugin"
        assert info.author == "dev"
        assert info.min_hgj_dev_version == "0.2.0"
        assert info.dependencies == ["other-plugin"]


class TestPluginLifecycle:
    """Test PluginLifecycle enum."""

    def test_init_value(self):
        assert PluginLifecycle.INIT.value == "init"

    def test_start_value(self):
        assert PluginLifecycle.START.value == "start"

    def test_stop_value(self):
        assert PluginLifecycle.STOP.value == "stop"

    def test_shutdown_value(self):
        assert PluginLifecycle.SHUTDOWN.value == "shutdown"


@pytest.mark.asyncio
class TestPlugin:
    """Test Plugin abstract base class via DummyPlugin."""

    async def test_plugin_info(self):
        plugin = DummyPlugin()
        assert plugin.info.name == "test-plugin"
        assert plugin.info.version == "1.0.0"

    async def test_initialize(self):
        plugin = DummyPlugin()
        assert not plugin.initialized
        await plugin.initialize()
        assert plugin.initialized

    async def test_initialize_with_config(self):
        plugin = DummyPlugin()
        await plugin.initialize({"key": "value"})
        assert plugin.initialized

    async def test_shutdown(self):
        plugin = DummyPlugin()
        await plugin.shutdown()
        assert plugin.shutdown_called

    async def test_on_event(self):
        plugin = DummyPlugin()
        await plugin.on_event("test_event", {"data": "value"})
        assert "test_event" in plugin.events

    async def test_get_commands_default(self):
        plugin = DummyPlugin()
        commands = plugin.get_commands()
        assert commands == {}

    async def test_get_tools_default(self):
        plugin = DummyPlugin()
        tools = plugin.get_tools()
        assert tools == []

    async def test_get_hooks_default(self):
        plugin = DummyPlugin()
        hooks = plugin.get_hooks()
        assert hooks == {}
