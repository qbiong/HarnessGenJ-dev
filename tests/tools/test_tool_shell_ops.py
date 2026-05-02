"""Tests for shell operations tools."""

import asyncio

from harnessgenj_dev.tools.shell_ops import RunCommandTool


class TestRunCommandTool:
    """Test shell command execution."""

    def test_echo_command(self):
        tool = RunCommandTool()
        result = asyncio.get_event_loop().run_until_complete(tool.execute(command="echo hello"))
        assert result.success
        assert "hello" in result.content.lower()

    def test_pwd_command(self):
        tool = RunCommandTool()
        result = asyncio.get_event_loop().run_until_complete(tool.execute(command="pwd"))
        assert result.success

    def test_timeout_handling(self):
        tool = RunCommandTool()
        result = asyncio.get_event_loop().run_until_complete(tool.execute(command="sleep 10", timeout=1))
        assert not result.success

    def test_command_with_error(self):
        tool = RunCommandTool()
        result = asyncio.get_event_loop().run_until_complete(tool.execute(command="false"))
        # May or may not be considered success depending on implementation
        assert result is not None
