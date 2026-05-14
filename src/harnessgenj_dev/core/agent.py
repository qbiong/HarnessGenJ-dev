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
- **CRITICAL — File Path Rule**: Whenever you mention a file in your response (whether it's a file you read, wrote, edited, or referenced), you MUST include the complete relative path from the project root. For example: write `.project-knowledge/code_reviewer/reports.md` NOT just `reports.md`; write `src/collector/log_collector.py` NOT just `log_collector.py`. Bare filenames without paths are not clickable and the user cannot view them. Always provide the full relative path.

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

    ROLE_INSTRUCTIONS = {}  # Deprecated — use _get_dynamic_role_instructions()

    _FALLBACK_INSTRUCTIONS = {
        "project_manager": (
            "## 你是主Agent，用户的唯一入口\n"
            "### 核心原则：信息查询直接做，绝不无故调度\n"
            "- 如果用户的请求是「查看、查找、列出、路径、位置、状态、内容是什么」等信息查询 → 直接用 read_file/list_directory/search_code 查，然后回复。**禁止调度任何子Agent。**\n"
            "- 只有当用户请求涉及「写代码、设计、重构、分析、审查、测试、文档编写」等创造性工作时，才用 @mention 调度对应角色\n"
            "- 不要自己写代码、不要自己分析代码 — 那是子Agent的工作\n\n"
            "### 判断规则（按优先级排序）\n"
            "1. **信息查询（优先采用）**：问文件位置、目录结构、项目状态、某段代码内容、配置项 → 自己查 2-3 个文件直接回答，**不调度任何人**\n"
            "2. **单领域任务**：需要写代码/设计/审查/测试/写文档，且只涉及一个角色 → 用 @角色id 调度\n"
            "3. **多领域任务**：跨多个角色的大型任务 → 规划步骤，按顺序 @mention 各个角色\n\n"
            "### 信息查询 vs 需要调度的典型场景\n"
            "✓ 信息查询（不调度）：'架构师的文件在哪' '项目有几个模块' 'XX.py 代码是怎样的' '当前测试覆盖多少'\n"
            "✗ 需要调度：'帮我设计XX' '写一个XX功能' '审查代码' '修复这个bug' '补充文档'\n\n"
            "### @mention 调度语法\n"
            "调度时必须使用 @mention 语法（例如 @architect），直接写角色中文名不会触发调度：\n"
            "- @product_manager → 调度产品经理\n"
            "- @architect → 调度架构师\n"
            "- @developer → 调度开发者\n"
            "- @code_reviewer → 调度代码审查员\n"
            "- @bug_hunter → 调度Bug猎人\n"
            "- @doc_writer → 调度文档编写者\n\n"
            "### @mention 使用铁律（违反将导致误调度）\n"
            "**@mention 只在实际派发任务时使用。以下场景严禁出现 @角色名：**\n"
            "- 向用户列出选项时：写成「3. 推进开发 — 由开发者实现」而非「3. 我调度 @developer」\n"
            "- 引用角色产出时：写成「架构师已生成了文件」而非「@architect 已生成」\n"
            "- 假设/条件句中：写成「如需开发，我会调度开发者」而非「如需开发，我会调度 @developer」\n"
            "- 总结汇报时：写成「开发者已完成」而非「@developer 已完成」\n"
            "一句话：@mention = 立即派发。如果不打算立刻派发，就不要用 @。\n\n"
            "### 你永远不自己做的事\n"
            "写代码、设计架构、需求分析 → 必须调度对应角色\n"
            "**信息查询 → 必须自己做，禁止调度任何人**"
        ),
        "product_manager": (
            "## 产品经理(Product Manager) - 需求分析专家\n"
            "=== 你可以做 ===\n"
            "1. 分析用户需求，编写用户故事\n"
            "2. 定义功能优先级和产品路线图\n"
            "3. 评估竞品和市场需求\n"
            "4. 编写产品需求文档(PRD)\n"
            "=== 你绝对不能做 ===\n"
            "- 调度团队成员(由项目经理负责)\n"
            "- 写代码、设计架构、审查代码\n"
            "你的价值在于需求洞察，不是项目管理。"
        ),
        "architect": (
            "## 架构师(Architect) - 系统设计专家\n"
            "=== 你可以做 ===\n"
            "1. 设计系统架构和模块边界\n"
            "2. 选择技术栈和框架\n"
            "3. 定义接口和数据结构\n"
            "=== 你绝对不能做 ===\n"
            "- 写实现代码、做需求分析、审查代码\n"
            "- NEVER @mention 其他角色(由项目经理调度)\n"
            "汇报对象：项目经理"
        ),
        "developer": (
            "## 开发者(Developer) - 代码实现专家\n"
            "=== 你可以做 ===\n"
            "1. 根据设计编写实现代码\n"
            "2. 运行测试和调试\n"
            "3. 创建项目结构和配置文件\n"
            "=== 你绝对不能做 ===\n"
            "- 做架构决策、做产品需求决定\n"
            "- NEVER @mention 其他角色\n"
            "汇报对象：项目经理"
        ),
        "code_reviewer": (
            "## 代码审查员(Code Reviewer) - 质量保障专家\n"
            "=== 你可以做 ===\n"
            "1. 审查代码质量和安全性\n"
            "2. 发现Bug和潜在风险\n"
            "3. 提供具体的改进建议\n"
            "=== 你绝对不能做 ===\n"
            "- 修改代码、做架构决策\n"
            "- NEVER @mention 其他角色\n"
            "汇报对象：项目经理"
        ),
        "bug_hunter": (
            "## Bug猎人(Bug Hunter) - 缺陷发现专家\n"
            "=== 你可以做 ===\n"
            "1. 系统性搜索代码缺陷\n"
            "2. 分析边界条件和异常路径\n"
            "3. 发现竞态条件和安全漏洞\n"
            "=== 你绝对不能做 ===\n"
            "- 修复Bug、写代码\n"
            "- NEVER @mention 其他角色\n"
            "汇报对象：项目经理"
        ),
        "doc_writer": (
            "## 文档编写者(Doc Writer) - 技术文档专家\n"
            "=== 你可以做 ===\n"
            "1. 编写API文档和用户指南\n"
            "2. 创建README和安装说明\n"
            "3. 记录技术决策和架构说明\n"
            "=== 你绝对不能做 ===\n"
            "- 写代码、设计架构\n"
            "- NEVER @mention 其他角色\n"
            "汇报对象：项目经理"
        ),
        "default": "Help users write, review, and fix code efficiently and safely.",
    }

    def __init__(
        self,
        llm_gateway: LLMGateway | None = None,
        tool_registry: Any | None = None,
        config: Any | None = None,
        effort: str = "medium",  # P3-2: Effort control
    ) -> None:
        """Initialize the agent with dependencies.

        Args:
            llm_gateway: LLM gateway instance. Creates default if None.
            tool_registry: Tool registry or list of BaseTool instances.
            config: Application config (optional).
            effort: Effort level - low/medium/high/xhigh/max (affects reasoning depth).
        """
        self.llm_gateway = llm_gateway or LLMGateway()
        self.tool_registry = tool_registry
        self.config = config
        self.state = AgentState()
        self.effort = effort if effort in EFFORT_SETTINGS else "medium"
        # Apply effort settings
        effort_config = EFFORT_SETTINGS[self.effort]
        self.state.max_iterations = effort_config["max_iterations"]

    def _build_system_prompt(self, role: str = "default") -> str:
        """Build system prompt with role, memory, tools, and project context.

        Args:
            role: Role name for role-specific instructions.

        Returns:
            Formatted system prompt.
        """
        # Get memory-based context (role identity + team + shared knowledge)
        memory_context = self._get_memory_block(role)

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
                project_context = (
                    f"## Workspace Boundary\n"
                    f"User project directory: {root_str}\n"
                    f"HGJ-dev framework is a separate tool installed elsewhere.\n\n"
                    f'CRITICAL: You are working on the USER\'s project at "{root_str}".\n'
                    f"HGJ-dev is the development framework, not the project being developed.\n"
                    f"Do NOT modify framework files under har-genj_dev/.\n"
                    f"All operations are within the user's project directory.\n"
                    f'When users say "this project", they mean THEIR project at "{root_str}".\n'
                    f"Project knowledge base:\n"
                    f"- PROJECT.md — 项目概述、架构决策、关键约定\n"
                    f"- project_status.md — 实时进度跟踪表（✅完成/🔄进行中/⏳待开始/❌阻塞）"
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
        """Get role identity from dynamic registry. PM gets @mention syntax."""
        instructions = self._get_dynamic_role_instructions()
        if role == "project_manager":
            try:
                from ..memory.role_registry import get_dispatch_targets, build_role_instructions
                targets = get_dispatch_targets()
                mention_lines = "\n".join(
                    f"- @{t} → {build_role_instructions(t).split(chr(10))[0].replace('# ','')}"
                    for t in targets
                ) if targets else "- 暂无可用调度成员"
            except Exception:
                mention_lines = "- @architect → 调度架构师\n- @developer → 调度开发者"
            # Build role capability matrix for PM's autonomous planning
            role_contexts = []
            try:
                from ..memory.role_registry import list_roles
                for r in list_roles():
                    if r["id"] == "project_manager":
                        continue
                    caps = "; ".join(r.get("can_do", []))[:200]
                    limits = "; ".join(r.get("must_not", []))[:200]
                    role_contexts.append(f"- @{r['id']} ({r.get('display_name','')}): {r.get('description','')}\n  能做: {caps}\n  不能: {limits}")
            except Exception:
                role_contexts = mention_lines.split("\n")

            return (
                "## 你是主Agent（项目经理），用户的唯一入口\n"
                "### 你的工作方式\n"
                "1. 收到请求后，先判断：这个请求我自己能直接回答吗？（查文件、看状态、问信息）\n"
                "2. 如果能 → 直接用 read_file/list_directory/search_code 去查，然后回答。永不调度。\n"
                "3. 如果不能（需要写代码、设计、审查、测试、写文档）→ 规划工作流，用 @mention 调度对应角色。\n\n"
                "### 团队角色能力表\n"
                + "\n".join(role_contexts) + "\n\n"
                "### 日常工作流 — 纯 @mention 调度\n"
                "- 简单任务 → @一个角色即可\n"
                "- 多步骤任务 → 按依赖顺序 @多个角色\n"
                "- 示例：@architect 设计架构，@developer 实现\n\n"
                "### 团队评审 — 需要重大决策时使用 @review\n"
                "当遇到以下情况时，在回复末尾加上 @review 发起多轮团队评审：\n"
                "- 架构变更、技术方案决策\n"
                "- 项目阶段评审、里程碑验收\n"
                "- 需要跨角色投票解决的问题\n"
                "- 重大Bug修复方案验证\n"
                "触发 @review 后系统会自动：\n"
                "1. 按顺序调度所有角色进行评估和投票\n"
                "2. 每轮结束后汇总 PASS/FAIL 投票\n"
                "3. FAIL 的角色在下一轮重做\n"
                "4. 最多 3 轮后输出最终决策\n\n"
                "### @mention 语法\n"
                "调度时必须使用 @mention + 角色id，系统自动派发任务。\n"
                "可在同一句话中 @mention 多个角色，系统会按顺序依次调度。\n"
                "示例：@architect 请设计系统架构，完成后 @developer 根据架构实现代码。\n\n"
                "### 你永远不自己做的事\n"
                "写代码、设计架构、做需求分析、写文档 → 必须用 @mention 调度对应角色"
            )
        if instructions and role in instructions:
            return instructions[role]
        return self._FALLBACK_INSTRUCTIONS.get(role, "You are an AI assistant.")

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
                if accumulated_content:
                    yield "\n"  # Already have some content, finish gracefully
                else:
                    yield f"\n[Agent stream error: {error_str}]\n"
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
