#!/usr/bin/env python3
"""Check HGJ framework completion status and report pending requirements.

Outputs structured JSON showing:
- Overall completion percentage per phase
- Pending tasks with priority
- Missing files
- TODO/FIXME items in source
- Whether all requirements are complete (boolean flag for automation)
"""
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent

# ============================================================
# Phase 1 Requirements (from docs/DEVELOPMENT_PLAN.md)
# ============================================================
PHASE_1_REQUIREMENTS = {
    "P1-T01": {
        "name": "LLM Gateway",
        "priority": "P0",
        "checks": [
            {"type": "file_exists", "path": "src/harnessgenj_dev/llm/gateway.py", "detail": "Main gateway module"},
            {"type": "file_exists", "path": "src/harnessgenj_dev/llm/providers/anthropic.py", "detail": "Anthropic provider"},
            {"type": "file_exists", "path": "src/harnessgenj_dev/llm/providers/openai.py", "detail": "OpenAI provider"},
            {"type": "file_exists", "path": "src/harnessgenj_dev/llm/providers/openrouter.py", "detail": "OpenRouter provider"},
            {"type": "file_exists", "path": "src/harnessgenj_dev/llm/providers/local.py", "detail": "Local model provider"},
            {"type": "no_placeholder", "path": "src/harnessgenj_dev/llm/gateway.py", "pattern": "Not yet implemented", "detail": "Gateway chat() must be implemented"},
            {"type": "no_placeholder", "path": "src/harnessgenj_dev/llm/streaming.py", "pattern": "pass", "detail": "Streaming must be implemented"},
        ],
    },
    "P1-T02": {
        "name": "Agent Core (ReAct Loop)",
        "priority": "P0",
        "checks": [
            {"type": "file_exists", "path": "src/harnessgenj_dev/core/agent.py", "detail": "Agent module"},
            {"type": "no_placeholder", "path": "src/harnessgenj_dev/core/agent.py", "pattern": "pass", "detail": "ReAct loop body must not be empty"},
            {"type": "no_placeholder", "path": "src/harnessgenj_dev/core/agent.py", "pattern": "not yet implemented", "detail": "Agent must be fully implemented"},
        ],
    },
    "P1-T03": {
        "name": "Tool Set",
        "priority": "P0",
        "checks": [
            {"type": "file_exists", "path": "src/harnessgenj_dev/tools/base.py", "detail": "Base tool class"},
            {"type": "file_exists", "path": "src/harnessgenj_dev/tools/registry.py", "detail": "Tool registry"},
            {"type": "file_exists", "path": "src/harnessgenj_dev/tools/file_ops.py", "detail": "File operations"},
            {"type": "file_exists", "path": "src/harnessgenj_dev/tools/shell_ops.py", "detail": "Shell operations"},
            {"type": "file_exists", "path": "src/harnessgenj_dev/tools/code_ops.py", "detail": "Code operations"},
            {"type": "file_exists", "path": "src/harnessgenj_dev/tools/test_ops.py", "detail": "Test operations"},
            {"type": "file_exists", "path": "src/harnessgenj_dev/tools/git_ops.py", "detail": "Git operations"},
        ],
    },
    "P1-T04": {
        "name": "Code Executor",
        "priority": "P0",
        "checks": [
            {"type": "file_exists", "path": "src/harnessgenj_dev/executor/sandbox.py", "detail": "Sandbox module"},
            {"type": "file_exists", "path": "src/harnessgenj_dev/executor/python_executor.py", "detail": "Python executor"},
            {"type": "file_exists", "path": "src/harnessgenj_dev/executor/shell_executor.py", "detail": "Shell executor"},
            {"type": "file_exists", "path": "src/harnessgenj_dev/executor/security.py", "detail": "Security module"},
            {"type": "security_integrated", "detail": "Security checks must be wired into executors"},
        ],
    },
    "P1-T05": {
        "name": "Interactive CLI/TUI",
        "priority": "P1",
        "checks": [
            {"type": "file_exists", "path": "src/harnessgenj_dev/tui/app.py", "detail": "TUI app"},
            {"type": "no_placeholder", "path": "src/harnessgenj_dev/tui/app.py", "pattern": "not yet implemented", "detail": "TUI must be implemented"},
            {"type": "file_exists", "path": "src/harnessgenj_dev/cli.py", "detail": "CLI entry point"},
        ],
    },
    "P1-T06": {
        "name": "Integration Tests",
        "priority": "P1",
        "checks": [
            {"type": "test_count_min", "min": 50, "detail": "At least 50 tests should exist"},
        ],
    },
}

# ============================================================
# Phase 2 Requirements
# ============================================================
PHASE_2_REQUIREMENTS = {
    "P2-T01": {
        "name": "Project Scanner - AST Analyzer",
        "priority": "P1",
        "checks": [
            {"type": "file_exists", "path": "src/harnessgenj_dev/scanner/ast_analyzer.py", "detail": "AST analyzer"},
            {"type": "file_exists", "path": "src/harnessgenj_dev/scanner/symbol_table.py", "detail": "Symbol table"},
            {"type": "file_exists", "path": "src/harnessgenj_dev/scanner/code_search.py", "detail": "Code search"},
        ],
    },
    "P2-T02": {
        "name": "HGJ Integration",
        "priority": "P1",
        "checks": [
            {"type": "dir_exists", "path": "src/harnessgenj_dev/hgj/", "detail": "HGJ integration module"},
        ],
    },
    "P2-T03": {
        "name": "Config Manager",
        "priority": "P1",
        "checks": [
            {"type": "file_exists", "path": "src/harnessgenj_dev/config.py", "detail": "Config manager"},
            {"type": "file_contains", "path": "src/harnessgenj_dev/config.py", "pattern": "yaml", "detail": "YAML persistence"},
        ],
    },
}

# ============================================================
# Phase 3 Requirements
# ============================================================
PHASE_3_REQUIREMENTS = {
    "P3-T01": {
        "name": "Plugin System",
        "priority": "P2",
        "checks": [
            {"type": "dir_exists", "path": "src/harnessgenj_dev/plugins/", "detail": "Plugin directory"},
        ],
    },
    "P3-T02": {
        "name": "Web Dashboard",
        "priority": "P2",
        "checks": [
            {"type": "dir_exists", "path": "src/harnessgenj_dev/web/", "detail": "Web dashboard directory"},
        ],
    },
}


def check_file_exists(path):
    full = PROJECT_ROOT / path
    return full.exists(), f"File missing: {path}" if not full.exists() else ""


def check_dir_exists(path):
    full = PROJECT_ROOT / path
    return full.is_dir(), f"Directory missing: {path}" if not full.is_dir() else ""


def check_no_placeholder(path, pattern):
    full = PROJECT_ROOT / path
    if not full.exists():
        return False, f"File not found: {path}"
    content = full.read_text(encoding="utf-8").lower()
    if pattern.lower() in content:
        return False, f"Placeholder found in {path}: '{pattern}'"
    return True, ""


def check_file_contains(path, pattern):
    full = PROJECT_ROOT / path
    if not full.exists():
        return False, f"File not found: {path}"
    content = full.read_text(encoding="utf-8")
    if pattern.lower() not in content.lower():
        return False, f"Pattern '{pattern}' not found in {path}"
    return True, ""


def check_security_integrated(**kwargs):
    """Check that security.py is wired into executors."""
    python_exec = PROJECT_ROOT / "src/harnessgenj_dev/executor/python_executor.py"
    shell_exec = PROJECT_ROOT / "src/harnessgenj_dev/executor/shell_executor.py"
    if not python_exec.exists() or not shell_exec.exists():
        return False, "Executor files missing"
    py_content = python_exec.read_text(encoding="utf-8")
    sh_content = shell_exec.read_text(encoding="utf-8")
    if "security" not in py_content.lower() or "is_safe" not in py_content.lower():
        return False, "Security not integrated into Python executor"
    if "security" not in sh_content.lower() or "is_safe" not in sh_content.lower():
        return False, "Security not integrated into Shell executor"
    return True, ""


def check_test_count_min(min_count=None, min=None, **kwargs):
    """Count actual test files."""
    threshold = min_count or min or 50
    test_dir = PROJECT_ROOT / "tests"
    if not test_dir.exists():
        return False, f"Tests directory missing (need {threshold}+ tests)"
    count = 0
    for f in test_dir.rglob("test_*.py"):
        count += 1
    if count < threshold:
        return False, f"Only {count} test files found, need {threshold}+"
    return True, ""


CHECK_DISPATCH = {
    "file_exists": check_file_exists,
    "dir_exists": check_dir_exists,
    "no_placeholder": check_no_placeholder,
    "file_contains": check_file_contains,
    "security_integrated": check_security_integrated,
    "test_count_min": check_test_count_min,
}


def evaluate_requirement(task_id, req):
    results = []
    all_pass = True
    for check in req["checks"]:
        check_type = check.pop("type")
        detail = check.pop("detail", "")  # Extract detail, don't pass to func
        func = CHECK_DISPATCH.get(check_type)
        if func is None:
            results.append({"check": check_type, "pass": False, "error": f"Unknown check type: {check_type}"})
            all_pass = False
            continue
        ok, msg = func(**check)
        if not ok:
            all_pass = False
        results.append({"check": check_type, "pass": ok, "detail": detail, "message": msg})
        check["type"] = check_type  # restore for next run
        check["detail"] = detail    # restore detail too
    return all_pass, results


def count_tests():
    """Count total number of test functions."""
    test_dir = PROJECT_ROOT / "tests"
    if not test_dir.exists():
        return 0
    count = 0
    for f in test_dir.rglob("test_*.py"):
        content = f.read_text(encoding="utf-8")
        for line in content.splitlines():
            if line.strip().startswith("def test_"):
                count += 1
    return count


def count_todos():
    """Count TODO/FIXME/HACK comments in source."""
    src = PROJECT_ROOT / "src"
    todos = []
    if not src.exists():
        return todos
    for f in src.rglob("*.py"):
        content = f.read_text(encoding="utf-8")
        for i, line in enumerate(content.splitlines(), 1):
            for keyword in ["TODO", "FIXME", "HACK"]:
                if keyword in line:
                    todos.append({
                        "file": str(f.relative_to(PROJECT_ROOT)),
                        "line": i,
                        "keyword": keyword,
                        "text": line.strip(),
                    })
    return todos


def main():
    all_phases = [
        ("Phase 1", PHASE_1_REQUIREMENTS),
        ("Phase 2", PHASE_2_REQUIREMENTS),
        ("Phase 3", PHASE_3_REQUIREMENTS),
    ]

    report = {
        "phases": {},
        "all_requirements_complete": True,
        "pending_items": [],
        "todo_count": 0,
        "test_count": 0,
    }

    for phase_name, requirements in all_phases:
        phase_report = {"tasks": {}, "completion_pct": 0, "complete_tasks": 0, "total_tasks": len(requirements)}
        completed = 0
        for task_id, req in requirements.items():
            passed, results = evaluate_requirement(task_id, req)
            if passed:
                completed += 1
            else:
                report["all_requirements_complete"] = False
                report["pending_items"].append({
                    "task_id": task_id,
                    "name": req["name"],
                    "priority": req["priority"],
                    "phase": phase_name,
                    "failed_checks": [r for r in results if not r["pass"]],
                })
            phase_report["tasks"][task_id] = {
                "name": req["name"],
                "priority": req["priority"],
                "passed": passed,
                "details": results,
            }
        phase_report["complete_tasks"] = completed
        phase_report["completion_pct"] = round(completed / len(requirements) * 100) if requirements else 0
        report["phases"][phase_name] = phase_report

    report["todo_count"] = len(count_todos())
    report["test_count"] = count_tests()

    # Output as JSON
    print(json.dumps(report, indent=2, ensure_ascii=False))

    # Also output human-readable summary to stderr
    print("\n" + "=" * 60, file=sys.stderr)
    print("HGJ Framework Requirement Check", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    for phase_name, requirements in all_phases:
        pr = report["phases"][phase_name]
        status = "COMPLETE" if pr["completion_pct"] == 100 else f"{pr['completion_pct']}% ({pr['complete_tasks']}/{pr['total_tasks']})"
        print(f"\n{phase_name}: {status}", file=sys.stderr)
        for task_id, task in pr["tasks"].items():
            icon = "PASS" if task["passed"] else "FAIL"
            print(f"  [{icon}] {task_id} - {task['name']} (P{task['priority'][-1]})", file=sys.stderr)
            if not task["passed"]:
                for d in task["details"]:
                    if not d["pass"]:
                        print(f"         -> {d.get('message', d.get('detail', ''))}", file=sys.stderr)

    print(f"\nTotal TODOs: {report['todo_count']}", file=sys.stderr)
    print(f"Total Tests: {report['test_count']}", file=sys.stderr)
    print(f"\nALL REQUIREMENTS COMPLETE: {report['all_requirements_complete']}", file=sys.stderr)

    # Return exit code based on completion status
    return 0 if report["all_requirements_complete"] else 1


if __name__ == "__main__":
    sys.exit(main())