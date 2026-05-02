#!/usr/bin/env python3
"""
harnessgenj_hook.py - Claude Code Hooks 桥接脚本 (自动生成)

功能:
1. PostToolUse: 自动记录文件操作到开发日志，触发对抗审查
2. PreToolUse: 安全检查，检测敏感信息泄露

此文件由 HarnessGenJ 自动生成
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime


def log_exception(e: Exception, context: str = "", level: int = 30) -> None:
    """记录异常信息到 stderr（独立实现，不依赖框架）"""
    level_str = "ERROR" if level >= 40 else "WARNING" if level >= 30 else "INFO"
    print(f"[HarnessGenJ {level_str}] [{context}] {type(e).__name__}: {e}", file=sys.stderr)


def get_project_root() -> Path:
    """获取项目根目录"""
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if project_dir:
        return Path(project_dir)
    script_path = Path(__file__).resolve()
    return script_path.parent.parent


def get_tool_input() -> dict:
    """获取工具输入参数"""
    # 尝试从环境变量获取
    tool_input = os.environ.get("TOOL_INPUT", "{}")
    try:
        return json.loads(tool_input)
    except json.JSONDecodeError:
        pass

    # 尝试从命令行参数获取
    if len(sys.argv) > 2:
        try:
            return json.loads(sys.argv[2])
        except json.JSONDecodeError:
            pass

    return {}


def append_to_development_log(content: str, context: str = "Hooks") -> bool:
    """追加内容到开发日志"""
    try:
        workspace = get_project_root() / ".harnessgenj"
        dev_log_path = workspace / "documents" / "development.md"
        dev_log_path.parent.mkdir(parents=True, exist_ok=True)

        if not dev_log_path.exists():
            dev_log_path.write_text(
                "# 开发日志\n\n此文件由 HarnessGenJ Hooks 自动维护。\n\n---\n",
                encoding="utf-8"
            )

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"\n## [{timestamp}] [{context}]\n\n{content}\n\n---\n"
        with open(dev_log_path, "a", encoding="utf-8") as f:
            f.write(entry)
        return True
    except Exception as e:
        log_exception(e, context="write_to_development_log", level=30)
        return False


def trigger_adversarial_review(file_path: str, content: str) -> dict[str, Any]:
    """
    触发对抗性审查（记录到积分系统并通过事件系统通知）

    Args:
        file_path: 文件路径
        content: 文件内容

    Returns:
        审查结果
    """
    result = {
        "file": file_path,
        "review_triggered": False,
        "issues": [],
    }

    # 检查是否是代码文件
    code_extensions = ['.py', '.java', '.kt', '.js', '.ts', '.tsx', '.go', '.rs']
    if not any(file_path.endswith(ext) for ext in code_extensions):
        return result

    # 记录到开发日志
    lines = content.count('\n') + 1 if content else 0
    log_content = f"Code file changed: `{file_path}` ({lines} lines)"
    append_to_development_log(log_content, context="AdversarialTrigger")

    # 写入事件文件，供 TriggerManager 消费
    try:
        workspace = get_project_root() / ".harnessgenj"
        events_dir = workspace / "events"
        events_dir.mkdir(parents=True, exist_ok=True)

        event_file = events_dir / f"event_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.json"
        event_data = {
            "type": "on_write_complete",
            "timestamp": datetime.now().isoformat(),
            "data": {
                "file_path": file_path,
                "lines": lines,
                "triggered_by": "hooks",
            }
        }

        with open(event_file, "w", encoding="utf-8") as f:
            json.dump(event_data, f, ensure_ascii=False, indent=2)

        result["review_triggered"] = True
    except Exception as e:
        log_exception(e, context="trigger_adversarial_review 事件写入", level=30)

    # 更新积分系统（如果存在）- 保持向后兼容
    try:
        workspace = get_project_root() / ".harnessgenj"
        scores_path = workspace / "scores.json"

        if scores_path.exists():
            with open(scores_path, "r", encoding="utf-8") as f:
                scores_data = json.load(f)

            # 添加事件记录
            event = {
                "timestamp": datetime.now().isoformat(),
                "type": "code_write",
                "file": file_path,
                "lines": lines,
                "triggered_by": "hooks",
            }
            if "events" not in scores_data:
                scores_data["events"] = []
            scores_data["events"].append(event)

            # 更新 developer 统计
            if "scores" in scores_data and "developer_1" in scores_data["scores"]:
                scores_data["scores"]["developer_1"]["total_tasks"] += 1

            with open(scores_path, "w", encoding="utf-8") as f:
                json.dump(scores_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log_exception(e, context="trigger_adversarial_review scores更新", level=30)

    return result


def handle_post_tool_use() -> int:
    """
    处理 PostToolUse 事件

    功能:
    1. 记录文件操作到开发日志
    2. 触发对抗性审查（更新积分系统）
    """
    tool_input = get_tool_input()
    tool_name = os.environ.get("TOOL_NAME", "")

    file_path = tool_input.get("file_path", tool_input.get("path", ""))
    content = tool_input.get("content", tool_input.get("new_string", ""))

    if not file_path:
        return 0

    # 记录操作
    action = "创建" if tool_name == "Write" else "修改"
    log_content = f"{action}文件: `{file_path}`"

    # 触发对抗性审查
    review_result = trigger_adversarial_review(file_path, content)
    if review_result["review_triggered"]:
        log_content += " [审查已触发]"

    # 输出提示信息
    print("[HarnessGenJ] 代码审查中...", file=sys.stderr)
    print(f"[HarnessGenJ] 已记录到开发日志: {file_path}", file=sys.stderr)

    return 0


def handle_pre_tool_use_security() -> int:
    """
    处理 PreToolUse 安全检查

    复用 SecurityHook 进行多语言安全检查
    """
    tool_input = get_tool_input()
    tool_name = os.environ.get("TOOL_NAME", "")

    file_path = tool_input.get("file_path", tool_input.get("path", ""))
    content = tool_input.get("content", tool_input.get("new_string", ""))

    if not content:
        if len(sys.argv) > 2:
            content = sys.argv[2]

    if not content:
        return 0

    # 尝试导入 SecurityHook 进行专业检查
    try:
        # 动态导入 SecurityHook
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "hooks",
            get_project_root() / ".claude" / "security_hook_standalone.py"
        )
        if spec and spec.loader:
            hooks_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(hooks_module)
            result = hooks_module.check_security(content, file_path)
            if result.get("warnings") or result.get("errors"):
                for err in result.get("errors", []):
                    print(f"[HarnessGenJ Security Error] {err}", file=sys.stderr)
                for warn in result.get("warnings", []):
                    print(f"[HarnessGenJ Security Warning] {warn}", file=sys.stderr)
                print("[HarnessGenJ] Suggest using environment variables or key management service for sensitive data", file=sys.stderr)
            return 0
    except Exception as e:
        log_exception(e, context="handle_pre_tool_use_security", level=30)

    # 回退到简化检查（当 SecurityHook 不可用时）
    high_risk_patterns = [
        "password", "secret", "api_key", "apikey", "token",
        "credential", "private_key", "access_key", "auth"
    ]
    warnings = []
    content_lower = content.lower()

    for pattern in high_risk_patterns:
        if pattern in content_lower:
            if "=" in content or ":" in content:
                lines = content.split("\n")
                for line in lines:
                    if pattern in line.lower() and ("=" in line or ":" in line):
                        if not line.strip().startswith("#") and not line.strip().startswith("//"):
                            warnings.append(f"Potential sensitive data: {pattern}")

    if warnings:
        print(f"[HarnessGenJ Security Warning] {', '.join(warnings)}", file=sys.stderr)
        print("[HarnessGenJ] Suggest using environment variables or key management service for sensitive data", file=sys.stderr)

    return 0


def handle_flush_state() -> int:
    """
    处理 Stop 事件 - 持久化状态
    """
    try:
        workspace = get_project_root() / ".harnessgenj"
        state_path = workspace / "state.json"

        if state_path.exists():
            # 更新最后同步时间
            with open(state_path, "r", encoding="utf-8") as f:
                state = json.load(f)

            state["last_hooks_sync"] = datetime.now().isoformat()

            with open(state_path, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)

            print("[HarnessGenJ] 状态已持久化", file=sys.stderr)
    except Exception as e:
        log_exception(e, context="handle_flush_state", level=30)

    return 0


def main():
    """主入口"""
    if len(sys.argv) < 2:
        print("Usage: harnessgenj_hook.py --post|--security|--flush-state", file=sys.stderr)
        return 1

    command = sys.argv[1]

    if command == "--post":
        return handle_post_tool_use()
    elif command == "--security":
        return handle_pre_tool_use_security()
    elif command == "--flush-state":
        return handle_flush_state()
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
