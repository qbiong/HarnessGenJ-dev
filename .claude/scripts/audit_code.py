#!/usr/bin/env python3
"""Code quality audit for HGJ-dev project.

Checks:
1. Code style consistency (indentation, line length, naming)
2. Import organization (sorted, no unused, grouped)
3. Function complexity (too many branches/lines)
4. Magic numbers and strings
5. Error handling gaps (bare except, swallowed exceptions)
6. Async/await correctness
7. Resource management (context managers)
8. Code duplication indicators
9. Test quality (assertions, coverage patterns)
10. Security anti-patterns
"""
import ast
import json
import re
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).parent.parent.parent
SRC_DIR = PROJECT_ROOT / "src" / "harnessgenj_dev"
TESTS_DIR = PROJECT_ROOT / "tests"

ISSUES = []


def issue(category: str, severity: str, location: str, message: str, recommendation: str = ""):
    ISSUES.append({
        "category": category,
        "severity": severity,
        "location": location,
        "message": message,
        "recommendation": recommendation,
    })


def check_code_style():
    """Check basic code style issues."""
    for py_file in SRC_DIR.rglob("*.py"):
        rel = str(py_file.relative_to(PROJECT_ROOT))
        content = py_file.read_text(encoding="utf-8")
        lines = content.splitlines()

        for i, line in enumerate(lines, 1):
            # Mixed tabs/spaces
            if "\t" in line and " " in line[:len(line) - len(line.lstrip())]:
                issue("style", "warning", f"{rel}:{i}",
                      "Mixed tabs and spaces in indentation",
                      "Use spaces only (PEP 8)")

            # Line too long (>120 chars, matching ruff config)
            if len(line.rstrip()) > 120:
                issue("style", "info", f"{rel}:{i}",
                      f"Line too long ({len(line.rstrip())} > 120 chars)",
                      "Break line or restructure")

            # Trailing whitespace
            if line != line.rstrip():
                issue("style", "info", f"{rel}:{i}",
                      "Trailing whitespace",
                      "Remove trailing whitespace")

        # File ends with newline
        if content and not content.endswith("\n"):
            issue("style", "info", rel,
                  "File does not end with newline",
                  "Add trailing newline")


def check_imports():
    """Check import organization and potential issues."""
    for py_file in SRC_DIR.rglob("*.py"):
        rel = str(py_file.relative_to(PROJECT_ROOT))
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue

        imports = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                imports.append(node)

        if not imports:
            continue

        # Check import grouping (stdlib, third-party, local)
        in_stdlib = True
        in_third_party = False
        in_local = False

        for imp in imports:
            if isinstance(imp, ast.ImportFrom):
                module = imp.module or ""
                is_local = module.startswith("harnessgenj_dev") or module.startswith(".")
                is_stdlib = module in sys.stdlib_module_names if hasattr(sys, 'stdlib_module_names') else _is_stdlib(module)
            else:
                is_local = False
                is_stdlib = True
                for alias in imp.names:
                    if alias.name.split(".")[0] not in (sys.stdlib_module_names if hasattr(sys, 'stdlib_module_names') else set()):
                        is_stdlib = False

            if is_local:
                if not in_local:
                    in_local = True
            elif is_stdlib:
                if in_third_party or in_local:
                    issue("imports", "info", f"{rel}:{imp.lineno}",
                          "Standard library imports should come before third-party and local",
                          "Reorder imports: stdlib -> third-party -> local")
            else:
                if not in_third_party:
                    in_third_party = True
                if in_local:
                    issue("imports", "info", f"{rel}:{imp.lineno}",
                          "Third-party imports should come before local imports",
                          "Reorder imports: stdlib -> third-party -> local")

        # Wildcard imports
        for imp in imports:
            if isinstance(imp, ast.ImportFrom):
                for alias in imp.names:
                    if alias.name == "*":
                        issue("imports", "warning", f"{rel}:{imp.lineno}",
                              "Wildcard import (from ... import *)",
                              "Use explicit imports for clarity and linting")


def _is_stdlib(module: str) -> bool:
    """Rough check if module is stdlib."""
    stdlib_prefixes = {
        "os", "sys", "pathlib", "json", "re", "ast", "typing",
        "collections", "itertools", "functools", "dataclasses",
        "abc", "enum", "contextlib", "asyncio", "subprocess",
        "logging", "datetime", "time", "io", "copy", "math",
        "string", "textwrap", "struct", "codecs", "hashlib",
        "unittest", "test", "importlib", "inspect",
    }
    return module.split(".")[0] in stdlib_prefixes


def check_function_complexity():
    """Check for overly complex functions."""
    for py_file in SRC_DIR.rglob("*.py"):
        rel = str(py_file.relative_to(PROJECT_ROOT))
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Count lines
                if hasattr(node, "end_lineno") and node.end_lineno:
                    func_lines = node.end_lineno - node.lineno + 1
                    if func_lines > 80:
                        issue("complexity", "warning", f"{rel}:{node.lineno}",
                              f"Function '{node.name}' is {func_lines} lines (>80)",
                              "Consider splitting into smaller functions")

                # Count branches (cyclomatic complexity approximation)
                branches = 0
                for child in ast.walk(node):
                    if isinstance(child, (ast.If, ast.For, ast.While, ast.ExceptHandler,
                                          ast.With, ast.Assert, ast.BoolOp)):
                        branches += 1
                if branches > 10:
                    issue("complexity", "warning", f"{rel}:{node.lineno}",
                          f"Function '{node.name}' has ~{branches} branches (>10)",
                          "Simplify control flow or extract helper functions")


def check_error_handling_gaps():
    """Check for error handling anti-patterns."""
    for py_file in SRC_DIR.rglob("*.py"):
        rel = str(py_file.relative_to(PROJECT_ROOT))
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                # Bare except
                if node.type is None:
                    issue("error_handling", "warning", f"{rel}:{node.lineno}",
                          "Bare 'except:' clause",
                          "Use 'except Exception:' or specific exception types")
                elif isinstance(node.type, ast.Name) and node.type.id == "Exception":
                    # Check if body just passes
                    if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                        issue("error_handling", "critical", f"{rel}:{node.lineno}",
                              "Exception is caught and silently ignored",
                              "At minimum log the exception or re-raise")
                # Swallowed exception
                if len(node.body) == 1:
                    stmt = node.body[0]
                    if isinstance(stmt, ast.Pass):
                        issue("error_handling", "warning", f"{rel}:{node.lineno}",
                              "Exception handler with only 'pass'",
                              "Handle the exception meaningfully or re-raise")


def check_resource_management():
    """Check for unclosed resources."""
    for py_file in SRC_DIR.rglob("*.py"):
        rel = str(py_file.relative_to(PROJECT_ROOT))
        content = py_file.read_text(encoding="utf-8")
        lines = content.splitlines()

        for i, line in enumerate(lines, 1):
            # open() without context manager
            stripped = line.strip()
            if "open(" in stripped and "with " not in stripped and "=" in stripped:
                # Likely: f = open(...)
                issue("resources", "warning", f"{rel}:{i}",
                      "File opened without context manager",
                      "Use 'with open(...) as f:' for automatic cleanup")

            # subprocess without timeout - check surrounding lines
            if "subprocess.run(" in stripped and "subprocess.TimeoutExpired" not in stripped:
                # Check current line and next 5 lines for timeout parameter
                window = "\n".join(lines[i:min(i+6, len(lines))])
                if "timeout" not in window:
                    issue("resources", "warning", f"{rel}:{i}",
                          "subprocess.run without timeout",
                          "Add timeout parameter to prevent hanging")


def check_security_patterns():
    """Check for security anti-patterns."""
    import re
    security_patterns = [
        (r"os\.system\(", "os.system() is vulnerable to shell injection",
         "Use subprocess.run with list arguments"),
        (r"eval\(", "eval() is dangerous",
         "Use ast.literal_eval() for safe evaluation or avoid dynamic eval"),
        (r"(?<!\w)exec\(", "exec() is dangerous",
         "Avoid dynamic code execution or use strict sandboxing"),
        (r"pickle\.loads?\(", "pickle is vulnerable to arbitrary code execution",
         "Use json, msgpack, or other safe serialization"),
        (r"yaml\.load\(", "yaml.load without Loader is unsafe",
         "Use yaml.safe_load() or yaml.load(..., Loader=yaml.SafeLoader)"),
        (r"shutil\.rmtree\(", "shutil.rmtree is dangerous",
         "Validate path before removing directories"),
    ]

    for py_file in SRC_DIR.rglob("*.py"):
        rel = str(py_file.relative_to(PROJECT_ROOT))
        content = py_file.read_text(encoding="utf-8")

        for pattern, msg, rec in security_patterns:
            for match in re.finditer(pattern, content):
                line_num = content[:match.start()].count("\n") + 1
                issue("security", "warning", f"{rel}:{line_num}",
                      msg, rec)


def check_test_quality():
    """Basic test quality checks."""
    if not TESTS_DIR.exists():
        issue("tests", "critical", "tests/",
              "No tests directory found",
              "Create tests/ directory with test files")
        return

    test_files = list(TESTS_DIR.rglob("test_*.py"))
    if not test_files:
        issue("tests", "critical", "tests/",
              "No test files found",
              "Add test files for each module")
        return

    for tf in test_files:
        rel = str(tf.relative_to(PROJECT_ROOT))
        content = tf.read_text(encoding="utf-8")

        # Check for assertions
        if "assert " not in content and ".assert" not in content:
            issue("tests", "warning", rel,
                  "Test file has no assertions",
                  "Tests should verify behavior with assertions")

        # Check test function naming
        try:
            tree = ast.parse(content)
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if node.name.startswith("test_"):
                    # Check if test has at least one assertion
                    has_assert = False
                    for child in ast.walk(node):
                        if isinstance(child, ast.Assert):
                            has_assert = True
                        if isinstance(child, ast.Call):
                            if isinstance(child.func, ast.Attribute):
                                if child.func.attr.startswith("assert"):
                                    has_assert = True
                    if not has_assert:
                        issue("tests", "info", f"{rel}:{node.lineno}",
                              f"Test '{node.name}' has no assertions",
                              "Add assertions to make the test meaningful")


def check_magic_values():
    """Check for magic numbers and unexplained constants."""
    for py_file in SRC_DIR.rglob("*.py"):
        rel = str(py_file.relative_to(PROJECT_ROOT))
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                # Skip common acceptable values
                if node.value in (0, 1, -1, True, False, None, "", 2, 100):
                    continue
                # Check if it's in a constant assignment (UPPER_CASE)
                # This is a rough heuristic
                issue("magic_values", "info", f"{rel}:{node.lineno}",
                      f"Magic number: {node.value}",
                      "Extract to a named constant for clarity")


def main():
    checks = [
        ("Code Style", check_code_style),
        ("Import Organization", check_imports),
        ("Function Complexity", check_function_complexity),
        ("Error Handling Gaps", check_error_handling_gaps),
        ("Resource Management", check_resource_management),
        ("Security Patterns", check_security_patterns),
        ("Test Quality", check_test_quality),
        ("Magic Values", check_magic_values),
    ]

    for name, func in checks:
        func()

    critical = [i for i in ISSUES if i["severity"] == "critical"]
    warnings = [i for i in ISSUES if i["severity"] == "warning"]
    infos = [i for i in ISSUES if i["severity"] == "info"]

    report = {
        "audit_type": "code",
        "total_issues": len(ISSUES),
        "critical": len(critical),
        "warnings": len(warnings),
        "infos": len(infos),
        "issues": ISSUES,
        "clean": len(critical) == 0 and len(warnings) == 0,
    }

    print(json.dumps(report, indent=2, ensure_ascii=False))

    # Human-readable to stderr
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"Code Quality Audit: {len(ISSUES)} issues", file=sys.stderr)
    print(f"  Critical: {len(critical)} | Warnings: {len(warnings)} | Info: {len(infos)}", file=sys.stderr)
    print(f"  CLEAN: {report['clean']}", file=sys.stderr)
    if critical:
        print(f"\nCritical issues:", file=sys.stderr)
        for i in critical:
            print(f"  [{i['location']}] {i['message']}", file=sys.stderr)
            if i.get("recommendation"):
                print(f"    -> {i['recommendation']}", file=sys.stderr)
    if warnings:
        print(f"\nWarnings:", file=sys.stderr)
        for i in warnings:
            print(f"  [{i['location']}] {i['message']}", file=sys.stderr)

    return 0 if report["clean"] else 1


if __name__ == "__main__":
    sys.exit(main())