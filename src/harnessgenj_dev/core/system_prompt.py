"""System prompt builder for different roles and contexts."""

from __future__ import annotations


class SystemPromptBuilder:
    """Build system prompts with role, context, and tool schema injection."""

    BASE_PROMPT = """You are HarnessGenJ-dev, an AI-powered development assistant.
You help users write, review, and fix code efficiently and safely."""

    def __init__(self) -> None:
        self._parts: list[str] = [self.BASE_PROMPT]

    def with_role(self, role: str) -> SystemPromptBuilder:
        """Inject role-specific instructions (Developer, CodeReviewer, etc.)."""
        role_prompts = {
            "developer": "You are acting as a Developer. Write clean, tested, production-ready code.",
            "code_reviewer": "You are acting as a CodeReviewer. Review code for bugs, security issues, and style.",
            "bug_hunter": "You are acting as a BugHunter. Find and fix defects in existing code.",
        }
        if prompt := role_prompts.get(role.lower()):
            self._parts.append(prompt)
        return self

    def with_context(self, context: str) -> SystemPromptBuilder:
        """Inject project context information."""
        self._parts.append(f"## Project Context\n{context}")
        return self

    def with_tools(self, tool_schemas: list[dict]) -> SystemPromptBuilder:
        """Inject tool schemas for the LLM."""
        self._parts.append(f"## Available Tools\n{tool_schemas}")
        return self

    def build(self) -> str:
        """Build the final system prompt."""
        return "\n\n".join(self._parts)
