"""Agent main loop - ReAct pattern implementation."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..llm.gateway import LLMGateway
from ..llm.models import LLMResponse
from ..plugins import get_hook_manager
from ..tools.registry import execute_tool, execute_tools_parallel, get_schemas
from ..utils.harness_md import get_harness_for_project
from .context_manager import get_context_manager

logger = logging.getLogger(__name__)

# Claude Code style hook events
HOOK_EVENTS = {
    "session_start": "Called when agent starts processing",
    "user_prompt_submit": "Called with user input before processing",
    "pre_tool_use": "Called before a tool is executed",
    "post_tool_use": "Called after a tool executes successfully",
    "post_tool_use_failure": "Called after a tool fails",
    "pre_compact": "Called before context compaction",
    "post_compact": "Called after context compaction",
    "stop": "Called when agent is interrupted",
    "stop_failure": "Called when stop fails",
    "error": "Called when an error occurs",
}


@dataclass
class ThoughtAction:
    """A single thought + optional action from the LLM."""

    thought: str
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None


@dataclass
class AgentState:
    """Current state of the agent."""

    conversation_history: list[dict[str, str]] = field(default_factory=list)
    iteration_count: int = 0
    max_iterations: int = 200
    is_running: bool = False


# P3-2: Effort control levels (affects temperature, max_tokens)
EFFORT_SETTINGS = {
    "low": {"temperature": 0.0, "max_tokens": 1024, "max_iterations": 5},
    "medium": {"temperature": 0.1, "max_tokens": 2048, "max_iterations": 10},
    "high": {"temperature": 0.3, "max_tokens": 4096, "max_iterations": 200},
    "xhigh": {"temperature": 0.5, "max_tokens": 8192, "max_iterations": 30},
    "max": {"temperature": 0.7, "max_tokens": 16384, "max_iterations": 50},
}


class Agent:
    """Main agent implementing ReAct loop.

    Cycle: Thought -> Action (tool call) -> Observation (tool result) -> Repeat
    Terminates when LLM produces no tool calls or max_iterations reached.
    """

    def __init__(
        self,
        llm_gateway: LLMGateway | None = None,
        tool_registry: Any | None = None,
        config: Any | None = None,
        effort: str = "medium",
    ) -> None:
        """Initialize the agent with dependencies."""
        self.llm_gateway = llm_gateway or LLMGateway()
        self.tool_registry = tool_registry
        self.config = config
        self.state = AgentState()
        self.effort = effort if effort in EFFORT_SETTINGS else "medium"
        effort_config = EFFORT_SETTINGS[self.effort]
        self.state.max_iterations = effort_config["max_iterations"]

    SYSTEM_PROMPT_TEMPLATE = """You are running inside HarnessGenJ-dev, an AI-driven development framework (similar to Claude Code / OpenClaw). You are an AI agent dispatched by this framework to help users with software development tasks.

## Your Identity
You are NOT HarnessGenJ-dev itself. You are an AI agent working within the HGJ-dev framework. The framework provides you with tools, memory, and team collaboration capabilities. Your job is to use these capabilities to help the USER develop their project.

## Calling Convention
{user_title_instruction}

## Framework Capabilities
- **Multi-Role Team**: You are currently acting as one role within a team. The Project Manager coordinates ALL tasks. Only PJM does dispatch. Non-PJM roles NEVER @mention.
- **Session Memory**: The framework maintains conversation history across sessions, allowing context to persist.
- **Project Management**: The framework tracks project structure, file indexes, and dependency graphs.
- **Adversarial Review**: Multiple roles can review each other's work to find bugs and improve quality.
- **Tool Access**: You have access to file operations, shell commands, code search, test execution, and Git operations.

{onboarding_instructions}

## Role Identity
{role_identity}

## Team Context
{team_context}

## Instructions
- The USER is asking you to work on THEIR project. Focus on their needs, not on the framework's internals.
- You have access to tools: read_file, write_file, edit_file, search_code, list_directory, run_command, run_test.
- When you need to perform an action, call the appropriate tool.
- After each tool call, you will receive the result (observation).
- Continue until the user's request is fully satisfied.
- You MUST use tools to do actual work. Do NOT just describe — actually CALL the tools.
- For large projects: use search_code to find relevant code instead of reading files one by one.
- Use list_directory to understand project structure before reading individual files.
- Be concise and focused. Minimize tool calls where possible.
- **ANTI-HALLUCINATION**: Describe what you DID, not what you WILL do. If you haven't called a tool yet, you haven't done the work. Saying "I will..." without a corresponding tool call is hallucination. Always call the tool first, then report the result.
- **CRITICAL — File Path Rule**: Whenever you mention a file in your response (whether it's a file you read, wrote, edited, or referenced), you MUST include the complete relative path from the project root. For example: write `.project-knowledge/code_reviewer/reports.md` NOT just `reports.md`; write `src/collector/log_collector.py` NOT just `log_collector.py`. Bare filenames without paths are not clickable and the user cannot view them. Always provide the full relative path.
- **CRITICAL — Knowledge File Update Rule**: After EVERY task completion, you MUST update your role's knowledge file with what was done, key decisions made, and files created/modified. This is MANDATORY — not optional. The knowledge files are the team's shared memory. If you skip this step, other team members will work with outdated information and make mistakes. Your knowledge file path is listed in your role identity section above.
- **Karpathy Coding Guidelines** (applies to all code-producing roles):
  1. **Think Before Coding** — State assumptions explicitly. If uncertain, ASK. Present tradeoffs, don't hide confusion. Push back when a simpler approach exists.
  2. **Simplicity First** — Minimum code to solve the problem. No speculative features, no abstractions for single-use code, no error handling for impossible scenarios. If 200 lines can be 50, rewrite.
  3. **Surgical Changes** — Touch only what you must. Don't \"improve\" adjacent code. Match existing style. Every changed line must trace to the user's request.
  4. **Goal-Driven Execution** — Turn tasks into verifiable goals. \"Fix the bug\" → \"Write a test that reproduces it, then fix.\" Loop until verified. Strong criteria let you work independently.

## Available Tools
{tool_descriptions}

## Rules
1. Always read a file before editing it
2. Run tests after making significant changes
3. Report errors clearly
4. Use the minimum number of tool calls needed
5. Remember your role identity and team members when responding

## Memory Context
{memory_context}

## Project Context
{project_context}

## Project Instructions (HARNESS.md)
{harness_instructions}
"""

    def _build_system_prompt(self, role: str = "default") -> str:
        """Build system prompt with role, memory, tools, and project context.

        Args:
            role: Role name for role-specific instructions.

        Returns:
            Formatted system prompt.
        """
        # Get memory-based context (role identity + team + shared knowledge)
        memory_context = self._get_memory_block(role)

        # Progressive Disclosure: build knowledge index (L1 metadata ~300 tokens)
        knowledge_index = self._build_knowledge_index()

        # Get tool descriptions
        tool_schemas = get_schemas()
        if tool_schemas:
            tool_descriptions = json.dumps(tool_schemas, indent=2, ensure_ascii=False)
        else:
            tool_descriptions = "No tools available."

        # Detect empty project and generate onboarding instructions
        onboarding_instructions = self._get_onboarding_instructions()

        # User title — loaded from settings for hot-reload (no restart needed)
        user_title = "用户"
        try:
            from pathlib import Path
            _sf = Path.home() / ".hgj-dev" / "web_settings.json"
            if _sf.exists():
                _sd = json.loads(_sf.read_text(encoding="utf-8"))
                user_title = _sd.get("user_title", "用户")
        except Exception:
            pass

        # Workspace context - this is the USER's project, NOT the framework
        project_context = "Working directory: " + os.getcwd() + "\n"
        if self.config:
            root = getattr(self.config, "project_root", None) or getattr(self.config, "project_path", None)
            if root:
                root_str = os.path.abspath(str(root))
                # Get GitHub URL from active project
                github_url = ""
                try:
                    from ..projects import get_active_project
                    active = get_active_project()
                    if active:
                        github_url = active.get("github_url", "")
                except Exception:
                    pass
                project_context = (
                    f"## Workspace Boundary\n"
                    f"User project directory: {root_str}\n"
                    f"HGJ-dev framework is a separate tool installed elsewhere.\n\n"
                    f'CRITICAL: You are working on the USER\'s project at "{root_str}".\n'
                    f"HGJ-dev is the development framework, not the project being developed.\n"
                    f"Do NOT modify framework files under har-genj_dev/.\n"
                    f"All operations are within the user's project directory.\n"
                    f'When users say "this project", they mean THEIR project at "{root_str}".\n'
                    + (f"GitHub repository: {github_url}\n" if github_url else "")
                    + f"Project knowledge base:\n"
                    f"- PROJECT.md — 项目概述、架构决策、关键约定\n"
                    f"- project_status.md — 实时进度跟踪表（✅完成/🔄进行中/⏳待开始/❌阻塞）\n"
                    f"- 如需更新 GitHub URL，使用 write_file 或 PATCH /api/projects/<name> 接口"
                    + (f"\n\n### 渐进式知识索引（共 {knowledge_index['count']} 个文件）\n"
                       f"先读索引了解可用文件，再按需读取具体文件。禁止逐个 read_file 扫描：\n"
                       + knowledge_index["index"])
                )

        # Role identity summary (short version for prompt)
        role_identity = self._get_role_identity_short(role)

        # Team context
        team_context = self._get_team_context()

        # HARNESS.md project instructions
        harness_instructions = self._get_harness_instructions()

        return self.SYSTEM_PROMPT_TEMPLATE.format(
            role_identity=role_identity,
            team_context=team_context,
            tool_descriptions=tool_descriptions,
            memory_context=memory_context,
            project_context=project_context,
            harness_instructions=harness_instructions,
            onboarding_instructions=onboarding_instructions,
            user_title_instruction=f"称呼约定：所有团队成员在交流时称呼用户为「{user_title}」。不要使用PM、老板或其他称呼，统一使用「{user_title}」。",
        )

    def _build_knowledge_index(self) -> dict[str, Any]:
        """Build a lightweight knowledge index (L1 metadata ~300 tokens).

        Scans .project-knowledge/ and returns a compact TOC so agents
        know what files exist without reading them all.
        """
        import json
        from pathlib import Path

        proj_root = None
        if self.config:
            root = getattr(self.config, "project_root", None) or getattr(self.config, "project_path", None)
            if root:
                proj_root = Path(str(root))
        if proj_root and proj_root.exists():
            kf_dir = proj_root / ".project-knowledge"
            entries = []
            if kf_dir.exists():
                for f in sorted(kf_dir.rglob("*")):
                    if f.is_file() and f.suffix in (".md", ".json", ".yaml", ".yml", ".txt"):
                        rel = f.relative_to(kf_dir)
                        size = f.stat().st_size
                        label = str(rel)
                        if f.name == "project_status.md":
                            label += " (✅ 项目全局进度，信息查询先读此文件)"
                        elif "adr" in str(rel).lower():
                            label += " (📐 架构决策记录)"
                        elif f.name == "design.md":
                            label += " (🏗️ 架构设计)"
                        elif f.name == "requirements.md":
                            label += " (📋 产品需求)"
                        elif f.name == "notes.md":
                            label += " (💻 开发者经验记录)"
                        elif f.name == "reports.md":
                            label += " (🔍 审查报告)"
                        elif f.name == "findings.md":
                            label += " (🐛 Bug 发现记录)"
                        elif f.name == "docs.md":
                            label += " (📝 文档状态)"
                        entries.append(f"- {label} ({size // 100 + 1}00B)")
            if entries:
                return {"count": len(entries), "index": "\n".join(entries)}
        return {"count": 0, "index": ""}

    def _get_onboarding_instructions(self) -> str:
        """Generate project initialization instructions for empty projects."""
        root = None
        if self.config:
            root = getattr(self.config, "project_root", None) or getattr(self.config, "project_path", None)
        if root and self._is_empty_project(root):
            return """## Project Onboarding — New Project Detected

The current project directory is empty. Follow this workflow to help the user start:

### Step 1: Guide Requirements Discovery
Ask the user to describe what they want to build. Use these questions:
- What is the project about? What problem does it solve?
- Who are the target users? (Web app, CLI tool, library, etc.)
- What is the tech stack preference? (language, framework, database)
- What are the key features for MVP?

### Step 2: Confirm Requirements
After the user responds, summarize your understanding and confirm:
- "Here's what I understand you want to build: [summary]. Is this correct?"

### Step 3: Generate Project Documents
Once confirmed, offer to create project documentation. Say:
- "I can generate a PROJECT.md describing the project structure, tech stack, and development plan. Would you like me to do that?"

If the user agrees, create PROJECT.md containing:
1. Project overview and goals
2. Tech stack and dependencies
3. Project structure (directory layout)
4. Module design
5. Development phases (MVP → iterations)
6. Coding standards and conventions

### Step 4: Begin Development
After documentation is confirmed, begin implementing the first phase:
- Initialize project structure (directories, config files)
- Set up the development environment (package.json, pyproject.toml, etc.)
- Implement the first feature from the plan

**IMPORTANT**: You are helping the user build their project from scratch. Take initiative. Lead the conversation. Don't wait for the user to give you every instruction — guide them through the process."""
        return ""

    @staticmethod
    def _is_empty_project(root: str) -> bool:
        """Check if the project directory is effectively empty (new project)."""
        root_path = Path(os.path.abspath(str(root)))
        if not root_path.exists():
            return True
        # Check for common indicators of an existing project
        indicators = [
            "package.json",
            "pyproject.toml",
            "Cargo.toml",
            "go.mod",
            "Makefile",
            "CMakeLists.txt",
            "setup.py",
            "setup.cfg",
            "pom.xml",
            "build.gradle",
            "Gemfile",
            "composer.json",
            "README.md",
            "PROJECT.md",
            "HARNESS.md",
            "src",
            "lib",
            "app",
            "main.py",
            "main.go",
            "index.js",
            ".git",
        ]
        has_content = False
        try:
            for _ in root_path.iterdir():
                has_content = True
                break
        except OSError:
            return True
        if not has_content:
            return True
        for indicator in indicators:
            if (root_path / indicator).exists():
                return False
        # Has files but no project indicators — likely empty/new
        files = list(root_path.glob("*"))
        # If only has very few non-indicator files, treat as empty
        if len(files) <= 2:
            return True
        return False

    def _get_harness_instructions(self) -> str:
        """Get project-specific instructions from HARNESS.md and AGENTS.md."""
        try:
            project_path = None
            if self.config:
                project_path = getattr(self.config, "project_path", None) or getattr(self.config, "project_root", None)

            instructions = []
            if project_path:
                project_root = Path(os.path.abspath(str(project_path)))
                # Load HARNESS.md
                harness = get_harness_for_project(project_path)
                if harness:
                    instructions.append("## HARNESS.md\n" + harness[:2000])
                # Load AGENTS.md (GitHub standard for AI agent context)
                agents_md = project_root / "AGENTS.md"
                if not agents_md.exists():
                    agents_md = project_root / ".github" / "AGENTS.md"
                try:
                    if agents_md.exists():
                        agents_content = agents_md.read_text(encoding="utf-8")[:1500]
                        instructions.append("## AGENTS.md (项目规范)\n" + agents_content)
                except Exception:
                    pass
            if instructions:
                return "\n\n".join(instructions)
            return "No HARNESS.md or AGENTS.md found. Create one to define project rules and AI agent instructions."
        except Exception as e:
            logger.debug(f"Failed to load project instructions: {e}")
            return "No project instructions available."

    def _get_memory_block(self, role: str) -> str:
        """Get memory context for the role."""
        try:
            from ..memory import MemoryManager

            mgr = MemoryManager()
            return mgr.build_prompt(role)
        except Exception:
            return "Memory system not available."

    @staticmethod
    def _get_dynamic_role_instructions() -> dict[str, str]:
        """Load role instructions from dynamic registry."""
        try:
            from ..memory.role_registry import get_all_role_instructions
            return get_all_role_instructions()
        except Exception:
            return {}

    def _get_role_identity_short(self, role: str) -> str:
        """Get role identity from dynamic registry (Single Source of Truth)."""
        try:
            from ..memory.role_registry import build_role_instructions, list_roles, get_dispatch_targets
            # Base role instructions from registry
            base = build_role_instructions(role)
            if role == "project_manager":
                # Append PM-specific orchestration context
                targets = get_dispatch_targets()
                role_contexts = []
                for r in list_roles():
                    if r["id"] == "project_manager":
                        continue
                    caps = "; ".join(r.get("can_do", []))[:200]
                    limits = "; ".join(r.get("must_not", []))[:200]
                    role_contexts.append(
                        f"- @{r['id']} ({r.get('display_name','')}): {r.get('description','')}\n"
                        f"  能做: {caps}\n  不能: {limits}"
                    )
                orchestration = (
                    "\n\n### PM 专属：团队编排\n"
                    "### 你的工作方式\n"
                    "1. 收到请求后，先判断：这个请求我自己能直接回答吗？（查文件、看状态、问信息）\n"
                    "2. 如果能 → 直接用工具查，然后回答。**永不调度。**\n"
                    "3. 如果不能 → 用 @mention 调度对应角色。\n\n"
                    "### 团队角色能力表\n"
                    + "\n".join(role_contexts) + "\n\n"
                    "### 渐进式知识索引（3 层加载，禁止预扫描）\n"
                    "系统提示词中已注入「渐进式知识索引」，列出了所有知识库文件的名称、大小和用途。\n"
                    "**禁止逐个 read_file 扫描项目目录。** 用法：\n"
                    "1. L1 索引：看索引就知道每个文件是干什么的（已注入，不需要再 read_file）\n"
                    "2. L2 关键文件：需要详情时，只读 1-2 个关键文件（如 project_status.md）\n"
                    "3. L3 引用文件：只有需要时才按需读取\n\n"
                    "### 派发前工具调用约束 ⚠️\n"
                    "**决定要 @mention 派发后，最多允许 3 次工具调用用于收集上下文：**\n"
                    "1. `read_file(.project-knowledge/project_status.md)` — 必须，了解全局状态\n"
                    "2. `read_file(...)` 或 `search_code(...)` — 可选，只读 1 个关键文件\n"
                    "3. 第 3 次用于确认后立即输出 @mention\n"
                    "**超限后果**：系统将强制终止你的思考循环并输出已有内容。不要试图提前读更多文件。\n"
                    "**禁止**：在派发前读取源代码文件（.py/.js/.ts）、测试文件（test_*）、配置文件（.yaml/.json）。\n"
                    "**替代方案**：需要了解代码时，使用 `search_code` 搜索关键字（1 次调用），不要逐个 read_file。\n\n"
                    "### @mention 使用铁律\n"
                    "- @mention = 立即派发。不打算派发就不要用 @\n"
                    "- 列选项/引用角色/假设句中严禁出现 @角色名\n"
                    "- 只有 @mention 语法触发派发，写中文角色名不会触发\n\n"
                    "### PM 核心规则\n"
                    "你的回复必须是以下两种之一：\n\n"
                    "方式 A（信息查询）：问状态/位置/进度 → 读 1-2 个文件直接回答，不用 @mention\n"
                    "方式 B（派发任务）：要改文件/写代码/修复/推送 → 第一句就用 @mention 派发对应角色\n\n"
                    "只要涉及改文件就是方式 B，不是方式 A\n\n"
                    "### 角色速查\n"
                    + "\n".join(role_contexts) + "\n\n"
                    "### @mention 语法\n"
                    "- @developer → 改文件/搜索/修复/推代码\n"
                    "- @architect → 设计/技术选型\n"
                    "- @code_reviewer → 审查代码\n"
                    "- @bug_hunter → 测试\n"
                    "- @doc_writer → 写文档\n\n"
                    "### 自我检查\n"
                    "如果你写了超过 100 字还没有 @mention → 你在自己干活，删掉重写。"
                )
                return base + orchestration
            return base
        except Exception:
            return f"## {role}\nYou are an AI agent working within the HGJ-dev framework."

    def _get_team_context(self) -> str:
        """Get team member info."""
        try:
            from ..memory.shared_memory import TEAM_MEMBERS

            members = "\n".join(f"- **@{r}**: {d}" for r, d in TEAM_MEMBERS.items())
            return (
                f"You are part of a multi-role team:\n{members}\n\n"
                "Use @mention to refer to team members. "
                "The Project Manager (@project_manager) is the default coordinator."
            )
        except Exception:
            return "You work as part of a multi-role team."

    def _get_tool_schemas(self) -> list[dict[str, Any]] | None:
        """Get tool schemas for LLM tool use.

        Returns:
            List of tool schemas or None if no tools registered.
        """
        schemas = get_schemas()
        return schemas if schemas else None

    async def _execute_tool_call(self, tool_call: dict[str, Any]) -> dict[str, str]:
        """Execute a single tool call and format the result.

        Args:
            tool_call: Dict with 'name' and 'input' (args), optionally 'id'.

        Returns:
            Observation message for the LLM with tool_call_id.
        """
        tool_name = tool_call.get("name", "unknown")
        tool_args = tool_call.get("input", {})
        tool_call_id = tool_call.get("id", f"call_{id(tool_call)}")

        logger.info("Executing tool: %s with args: %s", tool_name, tool_args)

        # Fire pre_tool_use hook
        hooks = get_hook_manager()
        await hooks.fire("pre_tool_use", tool_name=tool_name, tool_args=tool_args)

        try:
            result = await execute_tool(tool_name, **tool_args)
            if result.success:
                content = result.content or "Tool executed successfully (no output)."
                # Fire post_tool_use hook
                await hooks.fire(
                    "post_tool_use",
                    tool_name=tool_name,
                    tool_args=tool_args,
                    success=True,
                )
                return {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": f"[{tool_name}] Result:\n{content}",
                }
            else:
                # Fire post_tool_use_failure hook
                await hooks.fire(
                    "post_tool_use_failure",
                    tool_name=tool_name,
                    tool_args=tool_args,
                    error=result.error,
                )
                return {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": f"[{tool_name}] Error:\n{result.error}",
                }
        except Exception as exc:
            logger.exception("Tool execution failed: %s", tool_name)
            # Fire post_tool_use_failure hook
            await hooks.fire(
                "post_tool_use_failure",
                tool_name=tool_name,
                tool_args=tool_args,
                error=str(exc),
            )
            return {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": f"[{tool_name}] Exception:\n{exc}",
            }

    def _parse_tool_calls(self, response: LLMResponse) -> list[dict[str, Any]]:
        """Extract tool calls from LLM response.

        Args:
            response: LLM response that may contain tool_calls.

        Returns:
            List of tool call dicts.
        """
        if response.tool_calls:
            return response.tool_calls

        # Fallback: parse tool calls from content (for models that don't support structured tool calls)
        content = response.content.strip()
        tool_calls = []

        # Look for tool call patterns in content
        # Pattern: ```tool:tool_name\n{json args}\n```
        import re

        pattern = r"```tool:(\w+)\n(.*?)\n```"
        for match in re.finditer(pattern, content, re.DOTALL):
            name = match.group(1)
            try:
                args = json.loads(match.group(2))
                tool_calls.append({"name": name, "input": args})
            except json.JSONDecodeError:
                logger.warning("Failed to parse tool args for %s", name)

        return tool_calls

    async def run(self, user_input: str, role: str = "default") -> str:
        """Run the agent synchronously with the user input.

        Args:
            user_input: User's request/prompt.
            role: Role to use for this session.

        Returns:
            Final response text from the agent.
        """
        self.state.is_running = True

        # Don't clear history if already loaded from session
        if not self.state.conversation_history:
            self.state.iteration_count = 0
            system_prompt = self._build_system_prompt(role)
            self.state.conversation_history.append({"role": "system", "content": system_prompt})
            self.state.conversation_history.append({"role": "user", "content": user_input})
        elif self.state.conversation_history[-1].get("role") != "user":
            self.state.conversation_history.append({"role": "user", "content": user_input})

        # Fire session_start hook
        hooks = get_hook_manager()
        await hooks.fire("session_start", role=role)

        # Fire user_prompt_submit hook
        await hooks.fire("user_prompt_submit", prompt=user_input, role=role)

        try:
            return await self._react_loop()
        finally:
            self.state.is_running = False

    async def run_stream(self, user_input: str, role: str = "default") -> AsyncIterator[str]:
        """Run the agent with streaming output.

        Args:
            user_input: User's request/prompt.
            role: Role to use for this session.

        Yields:
            Text chunks as they arrive from the LLM.
        """
        self.state.is_running = True

        # Only add system prompt if history is empty
        if not self.state.conversation_history:
            self.state.iteration_count = 0
            system_prompt = self._build_system_prompt(role)
            self.state.conversation_history.append({"role": "system", "content": system_prompt})
        if not self.state.conversation_history or self.state.conversation_history[-1].get("role") != "user":
            self.state.conversation_history.append({"role": "user", "content": user_input})

        try:
            async for chunk in self._react_loop_stream():
                yield chunk
        finally:
            self.state.is_running = False

    async def _react_loop(self) -> str:
        """Main ReAct loop.

        1. Call LLM with conversation history and tool schemas
        2. If response has tool_calls, execute each tool
        3. Append tool results to conversation
        4. Repeat until no tool calls or max iterations
        5. Return final content

        Returns:
            Final text response from the LLM.
        """
        max_iter = self.state.max_iterations

        # 获取 ContextManager 用于压缩
        context_mgr = get_context_manager()

        for _ in range(max_iter):
            self.state.iteration_count += 1
            logger.debug("ReAct iteration %d", self.state.iteration_count)

            # Tier 1: 每次 API 调用前进行 micro-compact（清理旧 tool results）
            # 这是一个轻量级操作，不改变消息结构，只是清理旧内容
            if self.state.conversation_history:
                compaction_result = context_mgr.tier1_micro_compact(self.state.conversation_history)
                if compaction_result.tool_results_truncated > 0:
                    saved_tokens = compaction_result.original_tokens - compaction_result.compacted_tokens
                    logger.debug(
                        f"Tier 1 compaction: cleared {compaction_result.tool_results_truncated} "
                        f"old tool results, saved {saved_tokens} tokens"
                    )

            # 检查是否需要更高级别的压缩
            if context_mgr.needs_compaction(self.state.conversation_history):
                usage_pct = context_mgr.get_usage_ratio(self.state.conversation_history) * 100
                logger.warning(f"Context needs compaction: {usage_pct:.1f}% full")
                # 根据当前 token 使用率决定压缩层级
                current_tokens = context_mgr.get_usage_ratio(self.state.conversation_history)
                if current_tokens >= 0.95:
                    tier = 3
                elif current_tokens >= 0.85:
                    tier = 2
                else:
                    tier = 1

                result = context_mgr.compress(self.state.conversation_history, force_tier=tier)
                logger.info(
                    f"Tier {result.tier_applied} compaction: "
                    f"{result.original_tokens} -> {result.compacted_tokens} tokens, "
                    f"removed {result.messages_removed} messages"
                )

            # Call LLM with effort-based settings
            effort_config = EFFORT_SETTINGS.get(self.effort, EFFORT_SETTINGS["medium"])
            try:
                response = await self.llm_gateway.chat(
                    messages=self.state.conversation_history,
                    tools=self._get_tool_schemas(),
                    temperature=effort_config["temperature"],
                    max_tokens=effort_config["max_tokens"],
                )
            except Exception as exc:
                logger.exception("LLM call failed")
                # Fire error hook
                hooks = get_hook_manager()
                await hooks.fire("error", error=str(exc), context="llm_call")
                return f"Error: LLM call failed - {exc}"

            # Check for error response
            if response.error:
                return f"Error: {response.error}"

            # Append assistant response with tool_calls and reasoning if present
            assistant_msg = {"role": "assistant", "content": response.content}
            if response.reasoning_content:
                assistant_msg["reasoning_content"] = response.reasoning_content
            if response.tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.get("id", f"call_{i}"),
                        "type": "function",
                        "function": {
                            "name": tc.get("name", ""),
                            "arguments": json.dumps(tc.get("input", {})),
                        },
                    }
                    for i, tc in enumerate(response.tool_calls)
                ]
            self.state.conversation_history.append(assistant_msg)

            # Check for tool calls
            tool_calls = self._parse_tool_calls(response)
            if not tool_calls:
                # No tool calls -> we have our final answer
                logger.info(
                    "ReAct completed after %d iterations",
                    self.state.iteration_count,
                )
                return response.content

            # Execute tool calls with parallel execution for read-only tools
            # Claude Code 规则：只读工具并行，写操作工具顺序
            tool_call_dicts = [
                {
                    "name": tc.get("name", ""),
                    "input": tc.get("input", {}),
                    "id": tc.get("id", f"call_{i}"),
                }
                for i, tc in enumerate(tool_calls)
            ]
            results = await execute_tools_parallel(tool_call_dicts)

            for i, result in enumerate(results):
                observation = {
                    "role": "tool",
                    "content": result.content if result.success else f"Error: {result.error}",
                    "tool_call_id": tool_calls[i].get("id", f"call_{i}"),
                }
                self.state.conversation_history.append(observation)
                logger.debug(
                    "Tool observation %d: %s",
                    i,
                    observation["content"][:100],
                )

        # Max iterations reached
        logger.info("Agent reached max iterations (%d) in _react_loop", max_iter)
        return response.content or ""

    async def _react_loop_stream(self) -> AsyncIterator[str]:
        """Streaming version of ReAct loop.

        Yields text chunks from the LLM as they arrive.
        Tool execution happens transparently between LLM calls.
        """
        max_iter = self.state.max_iterations

        # 获取 ContextManager 用于压缩
        context_mgr = get_context_manager()

        for _ in range(max_iter):
            self.state.iteration_count += 1
            accumulated_content = ""

            # Tier 1: 每次 API 调用前进行 micro-compact
            if self.state.conversation_history:
                context_mgr.tier1_micro_compact(self.state.conversation_history)

            # 检查是否需要更高级别的压缩
            if context_mgr.needs_compaction(self.state.conversation_history):
                current_tokens = context_mgr.get_usage_ratio(self.state.conversation_history)
                tier = 3 if current_tokens >= 0.95 else (2 if current_tokens >= 0.85 else 1)
                result = context_mgr.compress(self.state.conversation_history, force_tier=tier)
                logger.info(
                    f"Tier {result.tier_applied} compaction (stream): "
                    f"{result.original_tokens} -> {result.compacted_tokens} tokens"
                )

            # Stream from LLM
            accumulated_tool_calls: list[dict[str, Any]] = []
            accumulated_reasoning_content = ""
            reasoning_phase = False  # True while we're seeing reasoning_content chunks
            try:
                async for chunk in self.llm_gateway.stream(
                    messages=self.state.conversation_history,
                    tools=self._get_tool_schemas(),
                ):
                    if chunk.reasoning_content:
                        accumulated_reasoning_content += chunk.reasoning_content
                        reasoning_phase = True
                    # Don't yield thinking markers — they're sent separately via 'thinking' message
                    if reasoning_phase and chunk.reasoning_content is None and chunk.content is None and accumulated_reasoning_content:
                        reasoning_phase = False
                    if chunk.error:
                        logger.warning("LLM stream chunk error: %s", chunk.error[:200])
                        yield "[Agent error: " + chunk.error[:100] + "]\n"
                        return

                    if chunk.content:
                        accumulated_content += chunk.content
                        yield chunk.content

                    if chunk.tool_calls:
                        # Merge streaming tool call fragments by index or ID
                        for tc in chunk.tool_calls:
                            tc_id = tc.get("id", "")
                            tc_idx = tc.get("index", -1)
                            func = tc.get("function", {})
                            existing = None
                            # Match by ID (first chunk) or by index (continuation chunks)
                            for existing_tc in accumulated_tool_calls:
                                if tc_id and existing_tc.get("id") == tc_id:
                                    existing = existing_tc
                                    break
                                if tc_idx >= 0 and existing_tc.get("index") == tc_idx:
                                    existing = existing_tc
                                    break
                            if existing:
                                prev_args = existing.get("function", {}).get("arguments", "")
                                new_args = func.get("arguments", "")
                                if prev_args and new_args:
                                    existing["function"]["arguments"] = prev_args + new_args
                                elif new_args:
                                    existing["function"]["arguments"] = new_args
                                # Preserve the real ID from first delta chunk
                                if tc_id and not existing.get("id"):
                                    existing["id"] = tc_id
                            else:
                                accumulated_tool_calls.append(tc)

                    if chunk.done:
                        break
            except Exception as exc:
                error_str = str(exc)[:200]
                logger.exception("LLM stream failed: %s", error_str)
                if "timeout" in error_str.lower() or "timed out" in error_str.lower():
                    user_msg = "\n[DeepSeek API 响应超时，请重试]\n"
                elif "rate" in error_str.lower() or "429" in error_str:
                    user_msg = "\n[请求频率过高，请稍后重试]\n"
                elif "401" in error_str or "403" in error_str:
                    user_msg = "\n[API Key 无效或权限不足]\n"
                else:
                    user_msg = f"\n[Agent stream error: {error_str}]\n"
                yield ("\n" + user_msg) if accumulated_content else user_msg
                return

            # Tool calls: use structured ones if available, else parse from content
            if accumulated_tool_calls:
                tool_calls = accumulated_tool_calls
            else:
                from ..llm.models import LLMResponse
                mock_response = LLMResponse(content=accumulated_content)
                tool_calls = self._parse_tool_calls(mock_response)

            # Append to history — include tool_calls + reasoning_content for API compatibility
            assistant_msg = {"role": "assistant", "content": accumulated_content}
            if accumulated_reasoning_content:
                assistant_msg["reasoning_content"] = accumulated_reasoning_content
            if tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.get("id", f"call_{i}"),
                        "type": "function",
                        "function": {
                            "name": tc.get("name", "") or tc.get("function", {}).get("name", ""),
                            "arguments": json.dumps(tc.get("input", {})) if "input" in tc
                                       else tc.get("function", {}).get("arguments", ""),
                        },
                    }
                    for i, tc in enumerate(tool_calls)
                ]
            self.state.conversation_history.append(assistant_msg)

            if not tool_calls:
                # No tool calls -> done
                yield "\n"
                return

            # Execute tools with parallel execution (for streaming version too)
            # Tool execution info goes to reasoning block, not main content
            accumulated_reasoning_content += "\n[执行工具中...]"

            tool_call_dicts = []
            for i, tc in enumerate(tool_calls):
                # Handle both streaming API format (function.name) and parsed format (name)
                if "function" in tc:
                    name = tc["function"].get("name", "")
                    try:
                        args = json.loads(tc["function"].get("arguments", "{}"))
                    except (json.JSONDecodeError, TypeError):
                        args = {"raw": tc["function"].get("arguments", "")}
                else:
                    name = tc.get("name", "")
                    args = tc.get("input", {})
                tool_call_dicts.append({
                    "name": name,
                    "input": args,
                    "id": tc.get("id", f"call_{i}"),
                })
            results = await execute_tools_parallel(tool_call_dicts)

            for i, result in enumerate(results):
                observation = {
                    "role": "tool",
                    "content": result.content if result.success else f"Error: {result.error}",
                    "tool_call_id": tool_calls[i].get("id", f"call_{i}"),
                }
                self.state.conversation_history.append(observation)

            # Accumulate tool execution summary into reasoning block (not into main content)
            tool_summary = "; ".join(
                f"{td.get('name', '?')}({str(td.get('input', {}))[:60]})"
                for td in tool_call_dicts
            )
            accumulated_reasoning_content += f"\n[工具: {tool_summary}]"

        # Max iterations — silently log, don't clutter output
        logger.info("Agent reached max iterations (%d)", max_iter)

    def interrupt(self) -> None:
        """Interrupt the current agent execution."""
        import asyncio

        from ..plugins import get_hook_manager

        self.state.is_running = False

        # Fire stop hook synchronously (fire and forget)
        hooks = get_hook_manager()
        try:
            asyncio.get_event_loop().run_until_complete(hooks.fire("stop", reason="user_interrupt"))
        except Exception:
            pass  # Best effort
