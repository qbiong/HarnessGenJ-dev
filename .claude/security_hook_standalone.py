#!/usr/bin/env python3
"""
security_hook_standalone.py - Standalone security check module

Reuses harnessgenj.harness.hooks.SecurityHook logic
Supports multi-language sensitive data detection
"""

import re
from typing import Any

# Multi-language sensitive patterns
LANGUAGE_PATTERNS = {
    "python": {
        "sensitive": [
            r'password\s*=\s*["\'][^"\']+["\']',
            r'api_key\s*=\s*["\'][^"\']+["\']',
            r'secret\s*=\s*["\'][^"\']+["\']',
            r'token\s*=\s*["\'][^"\']+["\']',
            r'credential\s*=\s*["\'][^"\']+["\']',
        ],
        "high_risk": ["password", "api_key", "secret", "token", "credential"],
    },
    "java": {
        "sensitive": [
            r'String\s+(password|apiKey|secret|token)\s*=\s*"[^"]+"',
            r'private\s+String\s+\w*[Pp]assword\w*\s*=\s*"[^"]+"',
            r'private\s+String\s+\w*[Tt]oken\w*\s*=\s*"[^"]+"',
            r'@Value\s*\(["\'][^"\']*(password|secret|token|key)["\']',
        ],
        "high_risk": ["password", "apiKey", "secret", "token", "credential"],
    },
    "kotlin": {
        "sensitive": [
            r'val\s+(password|apiKey|secret|token)\s*=\s*"[^"]+"',
            r'private\s+val\s+\w*[Pp]assword\w*\s*=',
            r'private\s+val\s+\w*[Tt]oken\w*\s*=',
            r'const\s+val\s+\w*[Kk]ey\w*\s*=\s*"[^"]+"',
        ],
        "high_risk": ["password", "apiKey", "secret", "token", "credential"],
    },
    "javascript": {
        "sensitive": [
            r'(const|let|var)\s+(password|apiKey|secret|token)\s*=\s*["\'][^"\']+["\']',
            r'process\.env\.\w*(PASSWORD|SECRET|TOKEN|KEY)',
        ],
        "high_risk": ["password", "apiKey", "secret", "token", "credential", "PRIVATE_KEY"],
    },
    "typescript": {
        "sensitive": [
            r'(const|let|var)\s+(password|apiKey|secret|token)\s*:\s*string\s*=\s*["\'][^"\']+["\']',
            r'process\.env\.\w*(PASSWORD|SECRET|TOKEN|KEY)',
        ],
        "high_risk": ["password", "apiKey", "secret", "token", "credential"],
    },
}

# Common high-risk patterns
HIGH_RISK_PATTERNS = [
    "password", "secret", "api_key", "token", "credential", "private_key"
]


def detect_language(file_path: str) -> str:
    """Detect language by file extension"""
    import os
    ext_map = {
        ".py": "python",
        ".java": "java",
        ".kt": "kotlin",
        ".kts": "kotlin",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
    }
    ext = os.path.splitext(file_path)[1].lower() if file_path else ""
    return ext_map.get(ext, "python")


def check_security(content: str, file_path: str = "") -> dict[str, Any]:
    """
    Execute security check

    Args:
        content: Content to check
        file_path: File path (for language detection)

    Returns:
        Check result {"errors": [], "warnings": []}
    """
    result = {
        "errors": [],
        "warnings": [],
        "passed": True,
    }

    if not content:
        return result

    # Detect language
    detected_lang = detect_language(file_path)
    lang_patterns = LANGUAGE_PATTERNS.get(detected_lang, LANGUAGE_PATTERNS["python"])

    # Check language-specific hardcoded sensitive data
    for pattern in lang_patterns["sensitive"]:
        try:
            if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
                result["errors"].append(f"[{detected_lang}] Hardcoded sensitive data: {pattern}")
                result["passed"] = False
        except re.error:
            pass

    # Check high-risk keywords
    for keyword in lang_patterns["high_risk"]:
        if keyword.lower() in content.lower():
            if "=" in content or ":" in content:
                result["warnings"].append(f"Potential sensitive data: {keyword}")

    # Check common dangerous patterns
    for pattern in HIGH_RISK_PATTERNS:
        if pattern.lower() in content.lower():
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if pattern.lower() in line.lower():
                    stripped = line.strip()
                    if not stripped.startswith('#') and not stripped.startswith('//') and not stripped.startswith('*'):
                        if '=' in line or ':' in line:
                            result["warnings"].append(f"Line {i+1}: potential sensitive config '{pattern}'")

    return result
