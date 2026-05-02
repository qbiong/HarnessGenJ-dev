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
    max_iterations: int = 20
    is_running: bool = False


# P3-2: Effort control levels (affects temperature, max_tokens)
EFFORT_SETTINGS = {
    "low": {"temperature": 0.0, "max_tokens": 1024, "max_iterations": 5},
    "medium": {"temperature": 0.1, "max_tokens": 2048, "max_iterations": 10},
    "high": {"temperature": 0.3, "max_tokens": 4096, "max_iterations": 20},
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

## Framework Capabilities
- **Multi-Role Team**: You are currently acting as one role within a team. The Product Manager coordinates tasks; @mentions can dispatch work to Developer, CodeReviewer, BugHunter, Architect, and DocWriter roles.
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
- You have access to tools that can read/write files, run shell commands, search code, run tests, and execute code.
- When you need to perform an action, call the appropriate tool.
- After each tool call, you will receive the result (observation).
- Continue until the user's request is fully satisfied.
- Be concise and focused. Only call tools when necessary.

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

    ROLE_INSTRUCTIONS = {
        "product_manager": (
            "## Product Manager\n"
            "**You CAN do:**\n"
            "- Understand user needs, gather and clarify requirements\n"
            "- Define project scope, features, and priorities\n"
            "- Create development plans and coordinate team members\n"
            "- Use @architect to delegate architecture design\n"
            "- Use @developer to delegate code implementation\n"
            "- Use @code_reviewer to delegate code review\n"
            "- Use @bug_hunter to delegate bug hunting\n"
            "- Use @doc_writer to delegate documentation\n"
            "- Generate PROJECT.md based on confirmed requirements\n\n"
            "**You MUST NOT do:**\n"
            "- Write any code (delegate to @developer)\n"
            "- Design system architecture (delegate to @architect)\n"
            "- Review code (delegate to @code_reviewer)\n"
            "- Debug or hunt bugs (delegate to @bug_hunter)\n"
            "- Write technical documentation (delegate to @doc_writer)\n\n"
            "**CRITICAL**: When any technical work is needed, you MUST use @mention to delegate. "
            "Never perform another role's work yourself. Your value is coordination, not execution."
        ),
        "architect": (
            "## Architect\n"
            "**You CAN do:**\n"
            "- Design system architecture and module boundaries\n"
            "- Choose tech stack, frameworks, and libraries\n"
            "- Define interfaces between components\n"
            "- Evaluate architectural trade-offs\n\n"
            "**You MUST NOT do:**\n"
            "- Write implementation code (delegate to @developer)\n"
            "- Review code quality (delegate to @code_reviewer)\n"
            "- Debug or hunt bugs (delegate to @bug_hunter)\n"
            "- Write user-facing documentation (delegate to @doc_writer)"
        ),
        "developer": (
            "## Developer\n"
            "**You CAN do:**\n"
            "- Write, modify, and refactor code\n"
            "- Implement features based on architect's design\n"
            "- Run tests, fix compilation errors\n"
            "- Create project structure and config files\n\n"
            "**You MUST NOT do:**\n"
            "- Make architectural decisions alone (consult @architect)\n"
            "- Self-review your own code (ask @code_reviewer)\n"
            "- Make product decisions (defer to @product_manager)\n"
            "- Hunt for bugs systematically (delegate to @bug_hunter)"
        ),
        "code_reviewer": (
            "## Code Reviewer\n"
            "**You CAN do:**\n"
            "- Review code for bugs, security issues, performance\n"
            "- Check adherence to coding standards\n"
            "- Identify anti-patterns and design smells\n"
            "- Provide specific, constructive feedback\n\n"
            "**You MUST NOT do:**\n"
            "- Write or modify code (delegate to @developer)\n"
            "- Make architectural decisions (delegate to @architect)\n"
            "- Make product scope decisions (delegate to @product_manager)"
        ),
        "bug_hunter": (
            "## Bug Hunter\n"
            "**You CAN do:**\n"
            "- Systematically analyze code for defects\n"
            "- Find edge cases, race conditions, resource leaks\n"
            "- Reproduce bugs and suggest root causes\n"
            "- Test boundary conditions and error paths\n\n"
            "**You MUST NOT do:**\n"
            "- Fix bugs (delegate to @developer)\n"
            "- Make architectural changes (delegate to @architect)\n"
            "- Make product decisions (delegate to @product_manager)"
        ),
        "doc_writer": (
            "## Documentation Writer\n"
            "**You CAN do:**\n"
            "- Write user guides, API docs, README files\n"
            "- Create tutorials and examples\n"
            "- Document technical designs and decisions\n\n"
            "**You MUST NOT do:**\n"
            "- Write code (delegate to @developer)\n"
            "- Design architecture (delegate to @architect)\n"
            "- Review code (delegate to @code_reviewer)"
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

        # Workspace context - this is the USER's project, NOT the framework
        project_context = "Working directory: " + os.getcwd()
        if self.config:
            root = getattr(self.config, "project_root", None) or getattr(self.config, "project_path", None)
            if root:
                root_str = os.path.abspath(str(root))
                project_context = (
                    f"## Workspace Boundary\n"
                    f"User project directory: {root_str}\n"
                    f"HGJ-dev framework is a separate tool installed elsewhere.\n\n"
                    f"CRITICAL: You are working on the USER's project at \"{root_str}\".\n"
                    f"HGJ-dev is the development framework, not the project being developed.\n"
                    f"Do NOT modify framework files under har-genj_dev/.\n"
                    f"All operations are within the user's project directory.\n"
                    f"When users say \"this project\", they mean THEIR project at \"{root_str}\"."
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
            "package.json", "pyproject.toml", "Cargo.toml", "go.mod",
            "Makefile", "CMakeLists.txt", "setup.py", "setup.cfg",
            "pom.xml", "build.gradle", "Gemfile", "composer.json",
            "README.md", "PROJECT.md", "HARNESS.md",
            "src", "lib", "app", "main.py", "main.go", "index.js",
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
        """Get project-specific instructions from the USER's HARNESS.md."""
        try:
            project_path = None
            if self.config:
                project_path = getattr(self.config, "project_path", None) or getattr(self.config, "project_root", None)

            if project_path:
                content = get_harness_for_project(project_path)
                if content:
                    max_len = 2000
                    if len(content) > max_len:
                        return "Project instructions (HARNESS.md):\n" + content[:max_len] + "\n...[truncated]"
                    return "Project instructions (HARNESS.md):\n" + content
            return "No HARNESS.md found in project. Create one to define project-specific rules."
        except Exception as e:
            logger.debug(f"Failed to load HARNESS.md: {e}")
            return "No HARNESS.md available."

    def _get_memory_block(self, role: str) -> str:
        """Get memory context for the role."""
        try:
            from ..memory import MemoryManager
            mgr = MemoryManager()
            return mgr.build_prompt(role)
        except Exception:
            return "Memory system not available."

    def _get_role_identity_short(self, role: str) -> str:
        """Get short role identity."""
        return self.ROLE_INSTRUCTIONS.get(role, self.ROLE_INSTRUCTIONS["default"])

    def _get_team_context(self) -> str:
        """Get team member info."""
        try:
            from ..memory.shared_memory import TEAM_MEMBERS
            members = "\n".join(
                f"- **@{r}**: {d}" for r, d in TEAM_MEMBERS.items()
            )
            return (
                f"You are part of a multi-role team:\n{members}\n\n"
                "Use @mention to refer to team members. "
                "The Product Manager (@product_manager) is the default coordinator."
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

    async def _execute_tool_call(
        self, tool_call: dict[str, Any]
    ) -> dict[str, str]:
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
        self.state.conversation_history.clear()
        self.state.iteration_count = 0

        # Fire session_start hook
        hooks = get_hook_manager()
        await hooks.fire("session_start", role=role)

        # Build system prompt
        system_prompt = self._build_system_prompt(role)
        self.state.conversation_history.append(
            {"role": "system", "content": system_prompt}
        )
        self.state.conversation_history.append(
            {"role": "user", "content": user_input}
        )

        # Fire user_prompt_submit hook
        await hooks.fire("user_prompt_submit", prompt=user_input, role=role)

        try:
            return await self._react_loop()
        finally:
            self.state.is_running = False

    async def run_stream(
        self, user_input: str, role: str = "default"
    ) -> AsyncIterator[str]:
        """Run the agent with streaming output.

        Args:
            user_input: User's request/prompt.
            role: Role to use for this session.

        Yields:
            Text chunks as they arrive from the LLM.
        """
        self.state.is_running = True
        self.state.iteration_count = 0

        # Only add system prompt if history is empty
        if not self.state.conversation_history:
            system_prompt = self._build_system_prompt(role)
            self.state.conversation_history.append(
                {"role": "system", "content": system_prompt}
            )
        elif self.state.conversation_history[-1].get("role") != "user":
            # Append user message only if last message isn't already the user input
            self.state.conversation_history.append(
                {"role": "user", "content": user_input}
            )
        self.state.conversation_history.append(
            {"role": "user", "content": user_input}
        )

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
                compaction_result = context_mgr.tier1_micro_compact(
                    self.state.conversation_history
                )
                if compaction_result.tool_results_truncated > 0:
                    saved_tokens = (
                        compaction_result.original_tokens - compaction_result.compacted_tokens
                    )
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
        return (
            f"Agent reached maximum iterations ({max_iter}). "
            f"Last response: {response.content}"
        )

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
                current_tokens = context_mgr.get_usage_ratio(
                    self.state.conversation_history
                )
                tier = 3 if current_tokens >= 0.95 else (2 if current_tokens >= 0.85 else 1)
                result = context_mgr.compress(
                    self.state.conversation_history, force_tier=tier
                )
                logger.info(
                    f"Tier {result.tier_applied} compaction (stream): "
                    f"{result.original_tokens} -> {result.compacted_tokens} tokens"
                )

            # Stream from LLM
            try:
                async for chunk in self.llm_gateway.stream(
                    messages=self.state.conversation_history,
                    tools=self._get_tool_schemas(),
                ):
                    if chunk.error:
                        yield f"\n[Error: {chunk.error}]\n"
                        return

                    if chunk.content:
                        accumulated_content += chunk.content
                        yield chunk.content

                    if chunk.done:
                        break
            except Exception as exc:
                logger.exception("LLM stream failed")
                yield f"\n[Error: LLM stream failed - {exc}]\n"
                return

            # Append to history
            self.state.conversation_history.append(
                {"role": "assistant", "content": accumulated_content}
            )

            # Check for tool calls (parse from accumulated content)
            # Create a mock response for parsing
            from ..llm.models import LLMResponse
            mock_response = LLMResponse(content=accumulated_content)
            tool_calls = self._parse_tool_calls(mock_response)

            if not tool_calls:
                # No tool calls -> done
                yield "\n"
                return

            # Execute tools with parallel execution (for streaming version too)
            # Execute tools and collect observations
            yield "\n[Executing tools...]\n"

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

        # Max iterations
        yield f"\n[Reached maximum iterations ({max_iter})]\n"

    def interrupt(self) -> None:
        """Interrupt the current agent execution."""
        import asyncio

        from ..plugins import get_hook_manager

        self.state.is_running = False

        # Fire stop hook synchronously (fire and forget)
        hooks = get_hook_manager()
        try:
            asyncio.get_event_loop().run_until_complete(
                hooks.fire("stop", reason="user_interrupt")
            )
        except Exception:
            pass  # Best effort
