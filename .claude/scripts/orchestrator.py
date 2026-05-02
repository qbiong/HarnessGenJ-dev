#!/usr/bin/env python3
"""HGJ Framework Automation Orchestrator.

This script produces a structured action plan for Claude Code to execute.
It does NOT implement code itself - it diagnoses the current state and
outputs what needs to be done.

Usage:
    python .claude/scripts/orchestrator.py

Output: JSON action plan on stdout, human-readable on stderr.
"""
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
STATE_FILE = Path(__file__).parent / ".hgj_state.json"


def get_last_activity():
    """Check last file modification time in src/ to estimate activity."""
    src = PROJECT_ROOT / "src"
    if not src.exists():
        return 0
    latest = 0
    for f in src.rglob("*.py"):
        mtime = f.stat().st_mtime
        if mtime > latest:
            latest = mtime
    return latest


def check_other_sessions():
    """Check if there's recent git activity suggesting another session is active."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "log", "--format=%at", "-n", "5"],
            cwd=str(PROJECT_ROOT),
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            timestamps = [int(t) for t in result.stdout.strip().split("\n") if t.strip()]
            if timestamps:
                return max(timestamps)
    except Exception:
        pass
    return 0


def load_state():
    """Load persisted state from previous runs."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "last_run": None,
        "last_action": None,
        "actions_taken": [],
        "audit_clean_count": 0,
        "requirements_complete": False,
    }


def save_state(state):
    """Persist state for next run."""
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def load_requirements_report():
    """Load the latest requirements check report."""
    report_file = Path(__file__).parent / ".hgj_requirements_report.json"
    if report_file.exists():
        return json.loads(report_file.read_text(encoding="utf-8"))
    return None


def load_architecture_report():
    """Load the latest architecture audit report."""
    report_file = Path(__file__).parent / ".hgj_architecture_report.json"
    if report_file.exists():
        return json.loads(report_file.read_text(encoding="utf-8"))
    return None


def load_code_report():
    """Load the latest code audit report."""
    report_file = Path(__file__).parent / ".hgj_code_report.json"
    if report_file.exists():
        return json.loads(report_file.read_text(encoding="utf-8"))
    return None


def main():
    state = load_state()
    now = time.time()

    # Activity detection
    last_file_activity = get_last_activity()
    last_git_activity = check_other_sessions()
    last_overall = max(last_file_activity, last_git_activity)
    seconds_idle = now - last_overall if last_overall > 0 else float("inf")
    minutes_idle = seconds_idle / 60

    state["last_run"] = now
    action_plan = {
        "idle_minutes": round(minutes_idle, 1),
        "should_proceed": minutes_idle > 30,  # Only proceed if idle > 30 min
        "mode": None,
        "actions": [],
        "priority": None,
    }

    if not action_plan["should_proceed"]:
        action_plan["mode"] = "WAIT"
        action_plan["message"] = (
            f"Project active - last activity {minutes_idle:.0f} min ago. "
            f"Waiting for 30+ min idle before proceeding."
        )
        print(json.dumps(action_plan, indent=2, ensure_ascii=False))
        save_state(state)
        return 0

    # Check requirements first
    req_report = load_requirements_report()
    arch_report = load_architecture_report()
    code_report = load_code_report()

    if req_report and not req_report.get("all_requirements_complete", False):
        # Phase 1: Drive requirements completion
        action_plan["mode"] = "DRIVE_REQUIREMENTS"
        pending = req_report.get("pending_items", [])

        # Sort by priority (P0 first, then P1, then P2)
        priority_order = {"P0": 0, "P1": 1, "P2": 2}
        pending.sort(key=lambda x: priority_order.get(x.get("priority", "P2"), 2))

        # Pick the highest priority pending item
        if pending:
            top = pending[0]
            action_plan["priority"] = top["task_id"]
            action_plan["actions"].append({
                "action": "implement",
                "task_id": top["task_id"],
                "name": top["name"],
                "priority": top["priority"],
                "phase": top.get("phase", "unknown"),
                "failed_checks": top.get("failed_checks", []),
                "instruction": (
                    f"Implement {top['name']} ({top['task_id']}, {top['priority']}). "
                    f"Focus on fixing the {len(top.get('failed_checks', []))} failed checks."
                ),
            })
            # Also queue the next 1-2 items for context
            for p in pending[1:3]:
                action_plan["actions"].append({
                    "action": "implement_next",
                    "task_id": p["task_id"],
                    "name": p["name"],
                    "priority": p["priority"],
                    "instruction": f"After completing {top['task_id']}, work on {p['name']} ({p['task_id']}).",
                })

    elif req_report and req_report.get("all_requirements_complete", False):
        # Phase 2: Architecture + Code audits
        arch_clean = arch_report.get("clean", False) if arch_report else False
        code_clean = code_report.get("clean", False) if code_report else False

        if not arch_clean:
            action_plan["mode"] = "ARCHITECTURE_AUDIT"
            action_plan["priority"] = "arch_fix"
            critical = arch_report.get("critical", 0)
            warnings = arch_report.get("warnings", 0)
            issues = arch_report.get("issues", [])[:10]  # Top 10
            action_plan["actions"].append({
                "action": "fix_architecture_issues",
                "critical_count": critical,
                "warning_count": warnings,
                "issues": issues,
                "instruction": (
                    f"Fix {critical} critical and {warnings} warning architecture issues. "
                    f"Start with critical issues first."
                ),
            })
        elif not code_clean:
            action_plan["mode"] = "CODE_AUDIT"
            action_plan["priority"] = "code_fix"
            critical = code_report.get("critical", 0)
            warnings = code_report.get("warnings", 0)
            issues = code_report.get("issues", [])[:10]
            action_plan["actions"].append({
                "action": "fix_code_issues",
                "critical_count": critical,
                "warning_count": warnings,
                "issues": issues,
                "instruction": (
                    f"Fix {critical} critical and {warnings} warning code quality issues. "
                    f"Start with critical issues first."
                ),
            })
        else:
            # Both clean!
            action_plan["mode"] = "ALL_CLEAN"
            action_plan["priority"] = "maintain"
            action_plan["actions"].append({
                "action": "report_clean",
                "instruction": (
                    "All requirements complete and both audits clean. "
                    "Verify by re-running audits. If still clean, report success."
                ),
            })
            state["audit_clean_count"] = state.get("audit_clean_count", 0) + 1
    else:
        # No reports available - need to generate them first
        action_plan["mode"] = "INITIAL_SCAN"
        action_plan["priority"] = "scan"
        action_plan["actions"].append({
            "action": "run_all_checks",
            "instruction": (
                "Run check_requirements.py, audit_architecture.py, and audit_code.py "
                "to generate baseline reports. Then act on the results."
            ),
        })

    save_state(state)
    print(json.dumps(action_plan, indent=2, ensure_ascii=False))

    # Human-readable
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"HGJ Automation Orchestrator", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)
    print(f"Idle time: {minutes_idle:.0f} minutes", file=sys.stderr)
    print(f"Should proceed: {action_plan['should_proceed']}", file=sys.stderr)
    print(f"Mode: {action_plan['mode']}", file=sys.stderr)
    print(f"Priority: {action_plan.get('priority', 'none')}", file=sys.stderr)
    for action in action_plan["actions"]:
        print(f"  -> {action.get('instruction', action.get('action', ''))}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())