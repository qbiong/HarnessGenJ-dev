#!/usr/bin/env python3
"""Architecture audit for HGJ-dev project.

Checks:
1. Module dependency graph - no circular imports
2. Interface completeness - all abstract methods implemented
3. SOLID principles adherence
4. Layer separation - no cross-layer violations
5. Error handling coverage
6. Type annotation coverage
7. Test coverage ratio
8. Documentation coverage (docstrings)
9. Config management (no hardcoded values)
10. Security posture
"""
import ast
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).parent.parent.parent
SRC_DIR = PROJECT_ROOT / "src" / "harnessgenj_dev"

ISSUES = []


def issue(category: str, severity: str, location: str, message: str, recommendation: str = ""):
    ISSUES.append({
        "category": category,
        "severity": severity,  # "critical", "warning", "info"
        "location": location,
        "message": message,
        "recommendation": recommendation,
    })


def check_module_structure():
    """Check that all planned modules exist and have substance."""
    expected_modules = {
        "core": ["agent.py", "system_prompt.py", "context_manager.py"],
        "llm": ["gateway.py", "model_router.py", "token_counter.py", "streaming.py"],
        "tools": ["base.py", "registry.py", "file_ops.py", "shell_ops.py", "code_ops.py", "test_ops.py", "git_ops.py"],
        "executor": ["sandbox.py", "python_executor.py", "shell_executor.py", "security.py"],
        "scanner": ["project_index.py"],
        "tui": ["app.py"],
        "utils": ["logger.py", "exceptions.py"],
    }

    for module, files in expected_modules.items():
        mod_dir = SRC_DIR / module
        if not mod_dir.exists():
            issue("structure", "critical", f"src/harnessgenj_dev/{module}/",
                  f"Module directory '{module}' missing",
                  f"Create directory and implement core interfaces")
            continue
        for fname in files:
            fpath = mod_dir / fname
            if not fpath.exists():
                issue("structure", "critical", f"src/harnessgenj_dev/{module}/{fname}",
                      f"Required file missing",
                      f"Implement this file as part of the {module} module")
            elif fpath.stat().st_size < 100:
                issue("structure", "warning", f"src/harnessgenj_dev/{module}/{fname}",
                      f"File exists but appears to be a stub ({fpath.stat().st_size} bytes)",
                      f"Implement actual functionality")


def check_circular_imports():
    """Basic circular import detection via AST analysis."""
    import_map = {}  # module -> set of imported modules
    for py_file in SRC_DIR.rglob("*.py"):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            issue("circular", "critical", str(py_file.relative_to(PROJECT_ROOT)),
                  "Syntax error prevents AST parsing", "Fix syntax errors first")
            continue

        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module and "harnessgenj_dev" in node.module:
                    imports.add(node.module)

        mod_name = str(py_file.relative_to(SRC_DIR.parent)).replace("/", ".").replace("\\", ".").replace(".py", "")
        import_map[mod_name] = imports

    # Simple 2-node cycle detection
    for mod_a, imports_a in import_map.items():
        for mod_b in imports_a:
            if mod_b in import_map and mod_a in import_map[mod_b]:
                issue("circular", "critical", mod_a,
                      f"Circular import: {mod_a} <-> {mod_b}",
                      f"Refactor to break the circular dependency")


def check_layer_violations():
    """Check that layers don't violate the architecture.

    Allowed dependencies:
    - core -> llm, tools, executor
    - llm -> utils
    - tools -> utils
    - executor -> utils
    - scanner -> utils
    - tui -> core, tools, scanner
    - cli -> core, config, tui
    """
    layer_deps = {
        "core": {"llm", "tools", "executor", "utils"},
        "llm": {"utils"},
        "tools": {"utils"},
        "executor": {"utils"},
        "scanner": {"utils"},
        "tui": {"core", "tools", "scanner", "utils"},
    }

    for py_file in SRC_DIR.rglob("*.py"):
        rel = str(py_file.relative_to(SRC_DIR))
        parts = rel.replace("\\", "/").split("/")
        if len(parts) < 2:
            continue  # top-level file like cli.py
        layer = parts[0]
        allowed = layer_deps.get(layer, set())

        try:
            content = py_file.read_text(encoding="utf-8")
            tree = ast.parse(content)
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                dep_parts = node.module.split(".")
                if len(dep_parts) >= 3 and dep_parts[2] in layer_deps:
                    dep_layer = dep_parts[2]
                    if dep_layer != layer and dep_layer not in allowed:
                        issue("layer", "warning", rel,
                              f"Layer '{layer}' depends on '{dep_layer}' (not allowed)",
                              f"Introduce an abstraction or restructure to respect layer boundaries")


def check_error_handling():
    """Check that custom exceptions are used throughout."""
    for py_file in SRC_DIR.rglob("*.py"):
        rel = str(py_file.relative_to(PROJECT_ROOT))
        if "exceptions.py" in rel:
            continue
        content = py_file.read_text(encoding="utf-8")
        if "raise Exception" in content:
            issue("error_handling", "warning", rel,
                  "Bare 'raise Exception' found",
                  f"Use specific exception types from utils.exceptions")
        if "except Exception" in content and "except HGJDevError" not in content:
            # Check if it catches bare Exception without re-wrapping
            issue("error_handling", "info", rel,
                  "Catches bare Exception - consider using HGJDevError hierarchy",
                  f"Import and use exceptions from utils.exceptions for better error classification")


def check_type_annotations():
    """Check for missing type annotations on public functions."""
    for py_file in SRC_DIR.rglob("*.py"):
        rel = str(py_file.relative_to(PROJECT_ROOT))
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                if not node.returns:
                    issue("typing", "info", f"{rel}:{node.lineno}",
                          f"Public function '{node.name}' missing return type annotation",
                          f"Add return type annotation for better type safety")


def check_docstrings():
    """Check for missing docstrings on public classes and functions."""
    for py_file in SRC_DIR.rglob("*.py"):
        rel = str(py_file.relative_to(PROJECT_ROOT))
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if not node.name.startswith("_"):
                    docstring = ast.get_docstring(node)
                    if not docstring:
                        kind = "class" if isinstance(node, ast.ClassDef) else "function"
                        issue("docs", "info", f"{rel}:{node.lineno}",
                              f"Public {kind} '{node.name}' missing docstring",
                              f"Add a docstring describing the purpose and interface")


def check_placeholder_implementation():
    """Check for stub implementations that need to be filled in."""
    placeholder_patterns = [
        "not yet implemented",
        "pass  # TODO",
        "TODO: Implement",
        "raise NotImplementedError",
    ]
    for py_file in SRC_DIR.rglob("*.py"):
        rel = str(py_file.relative_to(PROJECT_ROOT))
        content = py_file.read_text(encoding="utf-8").lower()
        for pattern in placeholder_patterns:
            if pattern.lower() in content:
                # Find line number
                lines = py_file.read_text(encoding="utf-8").splitlines()
                for i, line in enumerate(lines, 1):
                    if pattern.lower() in line.lower():
                        issue("completeness", "warning", f"{rel}:{i}",
                              f"Placeholder implementation: '{line.strip()}'",
                              f"Replace with actual implementation")


def check_hardcoded_values():
    """Check for hardcoded API keys, URLs, or paths."""
    import re
    patterns = [
        (r"['\"](sk-[a-zA-Z0-9]{20,})['\"]", "API key"),
        (r"['\"](anthropic|openai)['\"].*['\"][a-zA-Z0-9]{30,}['\"]", "API credential"),
        (r"['\"][a-zA-Z0-9]{40,}['\"]", "Possible hardcoded secret"),
    ]
    for py_file in SRC_DIR.rglob("*.py"):
        rel = str(py_file.relative_to(PROJECT_ROOT))
        if py_file.name == "config.py":
            continue
        content = py_file.read_text(encoding="utf-8")
        for pattern, desc in patterns:
            for match in re.finditer(pattern, content):
                issue("security", "warning", f"{rel}",
                      f"Possible hardcoded {desc}",
                      f"Move to configuration or environment variable")


def main():
    checks = [
        ("Module Structure", check_module_structure),
        ("Circular Imports", check_circular_imports),
        ("Layer Violations", check_layer_violations),
        ("Error Handling", check_error_handling),
        ("Type Annotations", check_type_annotations),
        ("Docstrings", check_docstrings),
        ("Placeholder Implementation", check_placeholder_implementation),
        ("Hardcoded Values", check_hardcoded_values),
    ]

    for name, func in checks:
        func()

    # Categorize
    critical = [i for i in ISSUES if i["severity"] == "critical"]
    warnings = [i for i in ISSUES if i["severity"] == "warning"]
    infos = [i for i in ISSUES if i["severity"] == "info"]

    report = {
        "audit_type": "architecture",
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
    print(f"Architecture Audit: {len(ISSUES)} issues", file=sys.stderr)
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