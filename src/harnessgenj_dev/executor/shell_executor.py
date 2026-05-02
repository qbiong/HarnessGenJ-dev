"""Shell command executor."""

from __future__ import annotations

import asyncio
import subprocess

from .sandbox import ExecutionResult, Sandbox
from .security import is_safe_to_run


class ShellExecutor(Sandbox):
    """Execute shell commands safely with security validation."""

    MAX_OUTPUT_BYTES = 10 * 1024  # 10KB

    async def execute(self, command: str, timeout: int = 30, cwd: str | None = None) -> ExecutionResult:
        """Run a shell command with security checks.

        Args:
            command: Shell command to execute.
            timeout: Maximum execution time in seconds.
            cwd: Working directory for the command.

        Returns:
            ExecutionResult with stdout, stderr, exit code, and timing.
        """
        # Security check before execution
        safe, reason = is_safe_to_run(command)
        if not safe:
            return ExecutionResult(
                success=False,
                stderr=f"Security check failed: {reason}",
                exit_code=1,
            )

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=cwd,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                out = stdout.decode("utf-8", errors="replace")
                err = stderr.decode("utf-8", errors="replace")

                if len(out) > self.MAX_OUTPUT_BYTES:
                    out = out[:self.MAX_OUTPUT_BYTES] + "\n[Output truncated]"
                if len(err) > self.MAX_OUTPUT_BYTES:
                    err = err[:self.MAX_OUTPUT_BYTES] + "\n[Output truncated]"

                return ExecutionResult(
                    success=proc.returncode == 0,
                    stdout=out,
                    stderr=err,
                    exit_code=proc.returncode or 0,
                )
            except TimeoutError:
                proc.kill()
                await proc.wait()
                return ExecutionResult(success=False, stderr="Command timed out", timed_out=True)
        except Exception as e:
            return ExecutionResult(success=False, stderr=str(e))
