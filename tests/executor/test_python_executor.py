"""Tests for Python executor."""
import asyncio
from harnessgenj_dev.executor.python_executor import PythonExecutor


class TestPythonExecutor:
    """Test Python code execution."""

    def test_simple_print(self):
        executor = PythonExecutor()
        result = asyncio.get_event_loop().run_until_complete(
            executor.execute("print('hello')", timeout=10)
        )
        assert result is not None

    def test_simple_math(self):
        executor = PythonExecutor()
        result = asyncio.get_event_loop().run_until_complete(
            executor.execute("print(2 + 2)", timeout=10)
        )
        assert result is not None

    def test_timeout(self):
        executor = PythonExecutor()
        result = asyncio.get_event_loop().run_until_complete(
            executor.execute("import time; time.sleep(100)", timeout=1)
        )
        assert not result.success
        assert result.timed_out

    def test_syntax_error(self):
        executor = PythonExecutor()
        result = asyncio.get_event_loop().run_until_complete(
            executor.execute("def foo(", timeout=10)
        )
        assert not result.success

    def test_custom_env(self):
        executor = PythonExecutor(env={"TEST_VAR": "test_value"})
        result = asyncio.get_event_loop().run_until_complete(
            executor.execute("import os; print(os.environ.get('TEST_VAR'))", timeout=10)
        )
        assert result is not None
