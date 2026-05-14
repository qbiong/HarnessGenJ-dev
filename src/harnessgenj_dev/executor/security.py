"""Security policies for code execution."""

from __future__ import annotations

import re
from enum import Enum


class SecurityLevel(str, Enum):
    """Security check severity levels."""

    STRICT = "strict"  # Block most operations, suitable for untrusted code
    MODERATE = "moderate"  # Block clearly dangerous operations, allow filesystem access
    PERMISSIVE = "permissive"  # Only block destructive operations


# Patterns that indicate potentially dangerous operations
DANGEROUS_PATTERNS: dict[str, list[str]] = {
    # Destructive operations (always blocked, all levels)
    "destructive": [
        r"rm\s+-rf\s+/",  # Recursive forced delete from root
        r"format\s+[a-zA-Z]:",  # Windows format drive
        r"sudo\s+.*(?:rm|mkfs|dd)",  # Dangerous sudo commands
        r"os\.system\s*\(.*rm\s+-rf",  # Python os.system rm -rf
        r"subprocess.*shell=True.*rm\s+-rf",  # Subprocess with rm -rf
        r"shutil\.rmtree\s*\(.*['\"]/",  # Delete from root
        r"dd\s+of=",  # Disk write
        r"chmod\s+777",  # Overly permissive file permissions
    ],
    # Dynamic code execution (blocked in strict, allowed in moderate/permissive)
    "dynamic_code": [
        r"\beval\s*\(",  # Dynamic evaluation
        r"\bexec\s*\(",  # Dynamic code execution
        r"__import__\s*\(.*['\"]os['\"]\)",  # Dynamic os import
        r"getattr\s*\(.*__import__",  # Dynamic import via getattr
        r"\bglobals\s*\(\)",  # Access global namespace
        r"\blocals\s*\(\)\.update",  # Modify local namespace
    ],
    # Network access (blocked in strict, allowed in moderate/permissive)
    "network": [
        r"\burllib\.request",  # URL request
        r"import\s+urllib\b",  # URL library
        r"from\s+urllib\b",  # URL library
        r"\brequests\b",  # HTTP requests library
        r"\bhttpx\b",  # Async HTTP library
        r"\bsocket\b",  # Raw socket access
    ],
    # Process creation (blocked in strict, allowed in moderate with limits)
    "process": [
        r"\bsubprocess\b",  # Subprocess import
        r"os\.system\s*\(",  # System command execution
        r"os\.popen\s*\(",  # Popen command execution
        r"os\.fork\s*\(",  # Process forking
        r"\bmultiprocessing\b",  # Multiprocessing
        r"\bthreading\b",  # Threading
    ],
    # Filesystem traversal (blocked in strict, allowed in moderate/permissive)
    "filesystem": [
        r"os\.listdir\s*\(",  # List directory
        r"os\.walk\s*\(",  # Walk directory tree
        r"\.iterdir\s*\(",  # Iterate directory
        r"os\.scandir\s*\(",  # Scan directory
        r"os\.getcwd\s*\(",  # Get current directory
    ],
}

# Patterns that are ALWAYS blocked regardless of security level
ALWAYS_BLOCKED = DANGEROUS_PATTERNS["destructive"]


def get_patterns_for_level(level: SecurityLevel) -> list[tuple[str, list[str]]]:
    """Get the pattern groups to check for a given security level.

    Args:
        level: Security level.

    Returns:
        List of (group_name, patterns) tuples to check.
    """
    always = [("destructive", ALWAYS_BLOCKED)]

    if level == SecurityLevel.STRICT:
        return always + [
            ("dynamic_code", DANGEROUS_PATTERNS["dynamic_code"]),
            ("network", DANGEROUS_PATTERNS["network"]),
            ("process", DANGEROUS_PATTERNS["process"]),
            ("filesystem", DANGEROUS_PATTERNS["filesystem"]),
        ]
    elif level == SecurityLevel.MODERATE:
        return always + [
            ("dynamic_code", DANGEROUS_PATTERNS["dynamic_code"]),
        ]
    else:  # PERMISSIVE
        return always


def check_dangerous_command(
    code: str,
    level: SecurityLevel = SecurityLevel.MODERATE,
) -> list[str]:
    """Check if code contains potentially dangerous operations.

    Args:
        code: Source code to check.
        level: Security level.

    Returns:
        List of matched dangerous pattern descriptions.
    """
    found = []
    patterns = get_patterns_for_level(level)

    for group_name, patterns_list in patterns:
        for pattern in patterns_list:
            if re.search(pattern, code):
                found.append(f"[{group_name}] {pattern}")

    return found


def is_safe_to_run(
    code: str,
    level: SecurityLevel = SecurityLevel.MODERATE,
) -> tuple[bool, str]:
    """Determine if code is safe to execute.

    Args:
        code: Source code to check.
        level: Security level.

    Returns:
        Tuple of (is_safe, reason).
    """
    dangerous = check_dangerous_command(code, level)
    if dangerous:
        return False, f"Dangerous patterns detected ({level.value}): {', '.join(dangerous)}"
    return True, ""
