"""Tests for executor module."""

import pytest


@pytest.mark.asyncio
async def test_python_executor():
    """Test Python code execution."""
    from harnessgenj_dev.executor.python_executor import PythonExecutor

    executor = PythonExecutor()
    result = await executor.execute('print("hello")')
    assert result.success
    assert "hello" in result.stdout


@pytest.mark.asyncio
async def test_python_executor_timeout():
    """Test Python executor timeout."""
    from harnessgenj_dev.executor.python_executor import PythonExecutor

    executor = PythonExecutor()
    result = await executor.execute("import time; time.sleep(10)", timeout=1)
    assert not result.success
    assert result.timed_out


@pytest.mark.asyncio
async def test_python_executor_stderr():
    """Test Python executor captures stderr separately."""
    from harnessgenj_dev.executor.python_executor import PythonExecutor

    executor = PythonExecutor()
    result = await executor.execute('import sys; print("error", file=sys.stderr)')
    assert result.success
    assert "error" in result.stderr


@pytest.mark.asyncio
async def test_python_executor_nonzero_exit():
    """Test Python executor handles non-zero exit codes."""
    from harnessgenj_dev.executor.python_executor import PythonExecutor

    executor = PythonExecutor()
    result = await executor.execute("import sys; sys.exit(42)")
    assert not result.success
    assert result.exit_code == 42


@pytest.mark.asyncio
async def test_python_executor_unicode():
    """Test Python executor handles Unicode correctly."""
    from harnessgenj_dev.executor.python_executor import PythonExecutor

    executor = PythonExecutor()
    result = await executor.execute('print("你好世界")')
    assert result.success
    assert "你好世界" in result.stdout


@pytest.mark.asyncio
async def test_python_executor_large_output():
    """Test Python executor truncates large output."""
    from harnessgenj_dev.executor.python_executor import PythonExecutor

    executor = PythonExecutor()
    code = 'print("x" * 20000)'
    result = await executor.execute(code)
    assert result.success
    assert "truncated" in result.stdout


@pytest.mark.asyncio
async def test_python_executor_stdin():
    """Test Python executor accepts stdin input."""
    from harnessgenj_dev.executor.python_executor import PythonExecutor

    executor = PythonExecutor()
    code = "import sys; print(sys.stdin.read().strip())"
    result = await executor.execute(code, stdin="hello from stdin")
    assert result.success
    assert "hello from stdin" in result.stdout


@pytest.mark.asyncio
async def test_python_executor_timing():
    """Test Python executor returns execution time."""
    from harnessgenj_dev.executor.python_executor import PythonExecutor

    executor = PythonExecutor()
    result = await executor.execute('print("timed")')
    assert result.success
    assert result.metadata is not None
    assert "elapsed_seconds" in result.metadata
    assert result.metadata["elapsed_seconds"] >= 0


@pytest.mark.asyncio
async def test_python_executor_env_isolation():
    """Test Python executor uses isolated environment."""
    from harnessgenj_dev.executor.python_executor import PythonExecutor

    executor = PythonExecutor()
    result = await executor.execute("import os; print(os.environ.get('PATH', ''))")
    assert result.success
    # PYTHONPATH should be empty in isolated env
    result2 = await executor.execute("import os; print(os.environ.get('PYTHONPATH', 'NOTSET'))")
    assert "NOTSET" in result2.stdout or result2.stdout.strip() == ""


@pytest.mark.asyncio
async def test_python_executor_security_check():
    """Test Python executor blocks dangerous code via security check."""
    from harnessgenj_dev.executor.python_executor import PythonExecutor

    executor = PythonExecutor()
    result = await executor.execute("eval(input())")
    assert not result.success
    assert "Security check failed" in result.stderr


@pytest.mark.asyncio
async def test_shell_executor():
    """Test shell command execution."""
    from harnessgenj_dev.executor.shell_executor import ShellExecutor

    executor = ShellExecutor()
    result = await executor.execute("echo hello")
    assert result.success
    assert "hello" in result.stdout


@pytest.mark.asyncio
async def test_shell_executor_timeout():
    """Test shell executor timeout."""
    from harnessgenj_dev.executor.shell_executor import ShellExecutor

    executor = ShellExecutor()
    result = await executor.execute("sleep 10", timeout=1)
    assert not result.success
    assert result.timed_out


@pytest.mark.asyncio
async def test_shell_executor_failure():
    """Test shell executor handles failed commands."""
    from harnessgenj_dev.executor.shell_executor import ShellExecutor

    executor = ShellExecutor()
    result = await executor.execute("exit 1")
    assert not result.success
    assert result.exit_code == 1


def test_security_checker_safe():
    """Test that safe code passes security check."""
    from harnessgenj_dev.executor.security import is_safe_to_run

    safe, _ = is_safe_to_run('print("hello")')
    assert safe


def test_security_checker_destructive():
    """Test that destructive commands are blocked."""
    from harnessgenj_dev.executor.security import is_safe_to_run, SecurityLevel

    unsafe, reason = is_safe_to_run("rm -rf /")
    assert not unsafe
    assert "Dangerous" in reason


def test_security_checker_dynamic_code_blocked_strict():
    """Test that dynamic code execution is blocked in strict mode."""
    from harnessgenj_dev.executor.security import is_safe_to_run, SecurityLevel

    safe, _ = is_safe_to_run("x = eval('1 + 1')", level=SecurityLevel.STRICT)
    assert not safe

    safe, _ = is_safe_to_run("exec('print(1)')", level=SecurityLevel.STRICT)
    assert not safe


def test_security_checker_network_blocked_strict():
    """Test that network access is blocked in strict mode."""
    from harnessgenj_dev.executor.security import is_safe_to_run, SecurityLevel

    safe, _ = is_safe_to_run("import requests; requests.get('http://example.com')", level=SecurityLevel.STRICT)
    assert not safe

    safe, _ = is_safe_to_run("import socket; s = socket.socket()", level=SecurityLevel.STRICT)
    assert not safe


def test_security_checker_process_blocked_strict():
    """Test that process creation is blocked in strict mode."""
    from harnessgenj_dev.executor.security import is_safe_to_run, SecurityLevel

    safe, _ = is_safe_to_run("import subprocess; subprocess.run(['ls'])", level=SecurityLevel.STRICT)
    assert not safe

    safe, _ = is_safe_to_run("os.system('ls')", level=SecurityLevel.STRICT)
    assert not safe


def test_security_checker_moderate_allows_process():
    """Test that moderate level allows process creation."""
    from harnessgenj_dev.executor.security import is_safe_to_run, SecurityLevel

    safe, _ = is_safe_to_run("import subprocess; subprocess.run(['ls'])", level=SecurityLevel.MODERATE)
    assert safe


def test_security_checker_permissive_allows_most():
    """Test that permissive level only blocks destructive operations."""
    from harnessgenj_dev.executor.security import is_safe_to_run, SecurityLevel

    safe, _ = is_safe_to_run("eval('1+1')", level=SecurityLevel.PERMISSIVE)
    assert safe

    safe, _ = is_safe_to_run("import requests", level=SecurityLevel.PERMISSIVE)
    assert safe

    # But destructive is still blocked
    unsafe, _ = is_safe_to_run("rm -rf /", level=SecurityLevel.PERMISSIVE)
    assert not unsafe


def test_security_checker_get_patterns():
    """Test pattern retrieval for security levels."""
    from harnessgenj_dev.executor.security import get_patterns_for_level, SecurityLevel

    strict_patterns = get_patterns_for_level(SecurityLevel.STRICT)
    moderate_patterns = get_patterns_for_level(SecurityLevel.MODERATE)
    permissive_patterns = get_patterns_for_level(SecurityLevel.PERMISSIVE)

    # Strict should have more patterns than moderate
    assert len(strict_patterns) > len(moderate_patterns)
    # Moderate should have more patterns than permissive
    assert len(moderate_patterns) > len(permissive_patterns)
    # All levels should include destructive patterns
    assert len(strict_patterns) >= 1
    assert len(moderate_patterns) >= 1
    assert len(permissive_patterns) >= 1
