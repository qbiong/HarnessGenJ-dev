"""Python code executor."""

from __future__ import annotations

import asyncio
import os
import subprocess
import tempfile
import time
from pathlib import Path

from .sandbox import ExecutionResult, Sandbox
from .security import is_safe_to_run


class PythonExecutor(Sandbox):
    """Execute Python code in an isolated subprocess."""

    MAX_OUTPUT_BYTES = 10 * 1024  # 10KB
    MAX_MEMORY_MB = 256  # 256MB memory limit

    def __init__(self, env: dict[str, str] | None = None) -> None:
        """Initialize with optional isolated environment.

        Args:
            env: Custom environment variables. If None, creates
                an isolated environment (no inheritance from parent).
        """
        self._custom_env = env

    def _get_env(self) -> dict[str, str]:
        """Get the execution environment."""
        if self._custom_env is not None:
            return self._custom_env

        # Create isolated environment (don't inherit parent)
        env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": "",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        return env

    async def execute(
        self,
        code: str,
        timeout: int = 30,
        stdin: str | None = None,
    ) -> ExecutionResult:
        """Run Python code safely with security checks and resource limits.

        Args:
            code: Python source code to execute.
            timeout: Maximum execution time in seconds.
            stdin: Optional stdin input to pipe to the process.

        Returns:
            ExecutionResult with stdout, stderr, exit code, and timing.
        """
        # Security check before execution
        safe, reason = is_safe_to_run(code)
        if not safe:
            return ExecutionResult(
                success=False,
                stderr=f"Security check failed: {reason}",
                exit_code=1,
            )

        start_time = time.time()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write("# -*- coding: utf-8 -*-\n")
            f.write(code)
            f.flush()
            tmp_path = f.name

        try:
            env = self._get_env()
            input_bytes = stdin.encode("utf-8") if stdin else None

            proc = await asyncio.create_subprocess_exec(
                "python",
                tmp_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE if stdin else None,
                env=env,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(input=input_bytes),
                    timeout=timeout,
                )
                elapsed = time.time() - start_time
                out = stdout.decode("utf-8", errors="replace")
                err = stderr.decode("utf-8", errors="replace")

                # Truncate large output
                if len(out) > self.MAX_OUTPUT_BYTES:
                    out = out[: self.MAX_OUTPUT_BYTES] + "\n[Output truncated]"
                if len(err) > self.MAX_OUTPUT_BYTES:
                    err = err[: self.MAX_OUTPUT_BYTES] + "\n[Output truncated]"

                return ExecutionResult(
                    success=proc.returncode == 0,
                    stdout=out,
                    stderr=err,
                    exit_code=proc.returncode or 0,
                    metadata={"elapsed_seconds": round(elapsed, 3)},
                )
            except TimeoutError:
                elapsed = time.time() - start_time
                proc.kill()
                await proc.wait()
                return ExecutionResult(
                    success=False,
                    stderr=f"Execution timed out after {timeout}s (ran for {elapsed:.1f}s)",
                    timed_out=True,
                )
        finally:
            Path(tmp_path).unlink(missing_ok=True)
