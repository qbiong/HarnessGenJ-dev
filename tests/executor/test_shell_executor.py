"""Tests for shell executor."""
import asyncio
from harnessgenj_dev.executor.shell_executor import ShellExecutor


class TestShellExecutor:
    """Test shell command execution."""

    def test_echo_command(self):
        executor = ShellExecutor()
        result = asyncio.get_event_loop().run_until_complete(
            executor.execute("echo hello", timeout=10)
        )
        assert result is not None

    def test_pwd_command(self):
        executor = ShellExecutor()
        result = asyncio.get_event_loop().run_until_complete(
            executor.execute("pwd", timeout=10)
        )
        assert result.success

    def test_command_timeout(self):
        executor = ShellExecutor()
        result = asyncio.get_event_loop().run_until_complete(
            executor.execute("sleep 100", timeout=1)
        )
        assert not result.success
        assert result.timed_out

    def test_failing_command(self):
        executor = ShellExecutor()
        result = asyncio.get_event_loop().run_until_complete(
            executor.execute("false", timeout=10)
        )
        assert not result.success

    def test_command_with_stderr(self):
        executor = ShellExecutor()
        result = asyncio.get_event_loop().run_until_complete(
            executor.execute("echo error >&2", timeout=10)
        )
        assert result is not None
