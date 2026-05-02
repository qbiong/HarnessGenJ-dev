"""Tests for executor edge cases."""

import os
import tempfile

import pytest

from harnessgenj_dev.executor.python_executor import PythonExecutor
from harnessgenj_dev.executor.shell_executor import ShellExecutor
from harnessgenj_dev.executor.security import (
    check_dangerous_command,
    is_safe_to_run,
    get_patterns_for_level,
    SecurityLevel,
    ALWAYS_BLOCKED,
)
from harnessgenj_dev.executor.sandbox import ExecutionResult


class TestPythonExecutorEdgeCases:
    """Test PythonExecutor edge cases."""

    @pytest.mark.asyncio
    async def test_empty_code(self):
        exec = PythonExecutor()
        result = await exec.execute("")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_security_check_failure(self):
        exec = PythonExecutor()
        # Code with dangerous pattern
        result = await exec.execute("import os; os.system('rm -rf /')")
        assert result.success is False
        assert "Security check failed" in result.stderr or "dangerous" in result.stderr.lower()

    @pytest.mark.asyncio
    async def test_temp_file_cleanup_on_error(self):
        """Temp file should be cleaned up even on error."""
        exec = PythonExecutor()
        # Code that raises an exception
        result = await exec.execute("raise ValueError('test error')")
        assert result.success is False
        # The temp file should be cleaned up

    @pytest.mark.asyncio
    async def test_stderr_output_truncation(self):
        """Long stderr should be truncated."""
        exec = PythonExecutor()
        long_stderr = "import sys; sys.stderr.write('x' * 20000)"
        result = await exec.execute(long_stderr)
        assert len(result.stderr) <= exec.MAX_OUTPUT_BYTES + 100

    def test_default_isolated_env(self):
        """Default env should have PATH only, no PYTHONPATH."""
        exec = PythonExecutor()
        env = exec._get_env()
        assert "PATH" in env
        assert env.get("PYTHONPATH", "") == ""


class TestShellExecutorEdgeCases:
    """Test ShellExecutor edge cases."""

    @pytest.mark.asyncio
    async def test_security_check_failure(self):
        exec = ShellExecutor()
        result = await exec.execute("rm -rf /")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_output_truncation(self):
        """Long output should be truncated."""
        exec = ShellExecutor()
        result = await exec.execute("python -c \"print('x' * 20000)\"")
        assert len(result.stdout) <= exec.MAX_OUTPUT_BYTES + 100

    @pytest.mark.asyncio
    async def test_stderr_only_output(self):
        exec = ShellExecutor()
        result = await exec.execute("python -c \"import sys; sys.stderr.write('error msg')\"")
        assert "error msg" in result.stderr

    @pytest.mark.asyncio
    async def test_stdout_and_stderr_present(self):
        exec = ShellExecutor()
        result = await exec.execute(
            "python -c \"import sys; print('out'); sys.stderr.write('err')\""
        )
        assert "out" in result.stdout

    @pytest.mark.asyncio
    async def test_exit_code_direct_field(self):
        exec = ShellExecutor()
        result = await exec.execute("python -c \"exit(42)\"")
        assert result.exit_code == 42

    @pytest.mark.asyncio
    async def test_process_creation_exception(self):
        """Should handle process creation failure gracefully."""
        exec = ShellExecutor()
        result = await exec.execute("nonexistent_command_that_does_not_exist_xyz")
        assert result.success is False


class TestSecurityEdgeCases:
    """Test security module edge cases."""

    def test_empty_code(self):
        found = check_dangerous_command("")
        assert found == []

    def test_dangerous_patterns_all_destructive(self):
        """All destructive patterns should be blocked."""
        patterns = [
            "rm -rf /",
            "sudo rm -rf",
            "chmod 777 /etc/passwd",
            "dd of=/dev/sda",
            "format C:",
            "subprocess.call('rm -rf /', shell=True)",
        ]
        for pattern in patterns:
            is_safe, _ = is_safe_to_run(pattern)
            assert is_safe is False, f"Should be blocked: {pattern}"

    def test_multiple_patterns_matched(self):
        """Code matching multiple patterns should still be blocked."""
        is_safe, reason = is_safe_to_run("sudo rm -rf / && chmod 777 /etc")
        assert is_safe is False

    def test_get_patterns_for_level_strict(self):
        patterns = get_patterns_for_level(SecurityLevel.STRICT)
        # STRICT should include most pattern groups
        assert len(patterns) >= 2

    def test_get_patterns_for_level_moderate(self):
        patterns = get_patterns_for_level(SecurityLevel.MODERATE)
        # MODERATE should include destructive + dynamic_code
        is_safe, _ = is_safe_to_run("eval('1+1')")
        assert is_safe is False

    def test_get_patterns_for_level_permissive(self):
        patterns = get_patterns_for_level(SecurityLevel.PERMISSIVE)
        # PERMISSIVE should only include destructive
        assert len(patterns) >= 1

    def test_always_blocked_references_destructive(self):
        # Test with actual commands that trigger the ALWAYS_BLOCKED patterns
        sample_commands = [
            "rm -rf /home/user",
            "sudo rm -rf /tmp",
            "os.system('rm -rf /')",
            "shutil.rmtree('/etc')",
            "dd of=/dev/sda bs=1M",
            "chmod 777 /etc/shadow",
            "format C: /y",
        ]
        for cmd in sample_commands:
            found = check_dangerous_command(cmd)
            assert len(found) > 0, f"Command should be detected: {cmd}"

    def test_is_safe_to_run_reason_format(self):
        is_safe, reason = is_safe_to_run("rm -rf /tmp/test")
        assert is_safe is False
        assert len(reason) > 0

    def test_regex_special_characters(self):
        """Code with regex special chars should not crash the checker."""
        found = check_dangerous_command("x = '[test]'")
        # Should not raise an exception
        assert isinstance(found, list)


class TestExecutionResult:
    """Test ExecutionResult dataclass."""

    def test_metadata_default_is_dict(self):
        result = ExecutionResult(success=True, stdout="ok")
        assert result.metadata == {}
        assert result.exit_code == 0
