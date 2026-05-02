"""Sandbox base class."""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result from code execution."""

    success: bool = True
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    timed_out: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SandboxConfig:
    """Sandbox configuration following Claude Code patterns."""

    # Filesystem isolation
    allowed_dirs: list[str] = field(default_factory=list)  # Empty = no restriction
    read_only_dirs: list[str] = field(default_factory=list)
    block_paths: list[str] = field(default_factory=list)

    # Network isolation
    allow_network: bool = True
    allowed_hosts: list[str] = field(default_factory=list)  # Empty = all allowed if network enabled
    proxy_url: str | None = None

    # Resource limits
    max_memory_mb: int = 256
    max_cpu_percent: int = 80
    max_execution_time: int = 30


# Global sandbox configuration
_default_config = SandboxConfig()


def set_default_sandbox_config(config: SandboxConfig) -> None:
    """Set the default sandbox configuration."""
    global _default_config
    _default_config = config
    logger.info(f"Sandbox config updated: network={config.allow_network}, allowed_dirs={config.allowed_dirs}")


def get_default_sandbox_config() -> SandboxConfig:
    """Get the current default sandbox configuration."""
    return _default_config


class Sandbox(ABC):
    """Base sandbox for safe code execution."""

    def __init__(self, config: SandboxConfig | None = None) -> None:
        """Initialize sandbox with optional custom config."""
        self.config = config or _default_config

    @abstractmethod
    async def execute(self, code: str, timeout: int = 30) -> ExecutionResult:
        """Execute code in a sandboxed environment.

        Args:
            code: Source code to execute.
            timeout: Maximum execution time in seconds.

        Returns:
            ExecutionResult with output and status.
        """

    def check_path_access(self, path: str, write: bool = False) -> tuple[bool, str]:
        """Check if a path is accessible within the sandbox.

        Args:
            path: Path to check.
            write: If True, check write access (stricter).

        Returns:
            Tuple of (allowed, reason).
        """
        try:
            abs_path = Path(path).resolve()
        except Exception as e:
            return False, f"Invalid path: {e}"

        # Check block paths
        for blocked in self.config.block_paths:
            if str(abs_path).startswith(blocked):
                return False, f"Path blocked: {blocked}"

        # Check allowed directories
        if self.config.allowed_dirs:
            allowed = False
            for allowed_dir in self.config.allowed_dirs:
                try:
                    abs_allowed = Path(allowed_dir).resolve()
                    # Check if path is under or equal to allowed dir
                    try:
                        abs_path.relative_to(abs_allowed)
                        allowed = True
                        break
                    except ValueError:
                        continue
                except Exception:
                    continue

            if not allowed:
                return False, f"Path not in allowed directories: {self.config.allowed_dirs}"

        # Check read-only directories
        if write and self.config.read_only_dirs:
            for ro_dir in self.config.read_only_dirs:
                try:
                    abs_ro = Path(ro_dir).resolve()
                    abs_path.relative_to(abs_ro)
                    return False, f"Write not allowed to read-only directory: {ro_dir}"
                except ValueError:
                    continue

        return True, ""

    def get_env_with_network_restriction(self) -> dict[str, str]:
        """Get environment variables with network restrictions.

        Returns:
            Dict of environment variables.
        """
        env = os.environ.copy()

        if not self.config.allow_network:
            # Block common network libraries
            env.pop("HTTP_PROXY", None)
            env.pop("HTTPS_PROXY", None)
            env.pop("http_proxy", None)
            env.pop("https_proxy", None)
            # Add NO_PROXY to block all
            env["NO_PROXY"] = "*"

        if self.config.proxy_url:
            env["HTTP_PROXY"] = self.config.proxy_url
            env["HTTPS_PROXY"] = self.config.proxy_url

        return env
