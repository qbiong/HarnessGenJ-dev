"""Tests for sandbox module."""

from harnessgenj_dev.executor.sandbox import ExecutionResult


class TestExecutionResult:
    """Test ExecutionResult dataclass."""

    def test_success_result(self):
        r = ExecutionResult(success=True, stdout="OK")
        assert r.success is True
        assert r.stdout == "OK"

    def test_error_result(self):
        r = ExecutionResult(success=False, stderr="error")
        assert r.success is False
        assert r.stderr == "error"

    def test_result_with_metadata(self):
        r = ExecutionResult(success=True, metadata={"time": 1.5})
        assert r.metadata["time"] == 1.5

    def test_timed_out_flag(self):
        r = ExecutionResult(success=False, stderr="timeout", timed_out=True)
        assert r.timed_out is True

    def test_exit_code(self):
        r = ExecutionResult(success=False, exit_code=127)
        assert r.exit_code == 127

    def test_default_values(self):
        r = ExecutionResult()
        assert r.success is True
        assert r.stdout == ""
        assert r.stderr == ""
        assert r.exit_code == 0
        assert r.timed_out is False
        assert r.metadata == {}
