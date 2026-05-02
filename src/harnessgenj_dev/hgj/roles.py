"""HGJ Role Management.

Defines the standard HGJ roles and their integration with
HGJ-dev's system prompt builder and agent core.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class HGJRole:
    """A role in the HGJ framework.

    Attributes:
        name: Role identifier (e.g., 'developer', 'code_reviewer').
        description: Human-readable role description.
        system_prompt: Role-specific system prompt template.
        tools: List of tool names available to this role.
        max_turns: Maximum conversation turns for this role.
    """

    name: str
    description: str
    system_prompt: str
    tools: list[str] = field(default_factory=list)
    max_turns: int = 20


# Standard HGJ role definitions
DEVELOPER_ROLE = HGJRole(
    name="developer",
    description="Writes code, fixes bugs, and implements features",
    system_prompt=(
        "You are a skilled software developer. "
        "Follow SOLID principles, write clean and tested code. "
        "Always read existing code before modifying it. "
        "Use available tools to accomplish tasks efficiently."
    ),
    tools=["read_file", "write_file", "edit_file", "run_command", "run_tests"],
    max_turns=30,
)

CODE_REVIEWER_ROLE = HGJRole(
    name="code_reviewer",
    description="Reviews code for quality, security, and best practices",
    system_prompt=(
        "You are an experienced code reviewer. "
        "Focus on correctness, security, readability, and maintainability. "
        "Identify potential bugs, security vulnerabilities, and design issues. "
        "Provide constructive feedback with specific examples."
    ),
    tools=["read_file", "search_code", "run_command"],
    max_turns=15,
)

BUG_HUNTER_ROLE = HGJRole(
    name="bug_hunter",
    description="Finds and diagnoses bugs in the codebase",
    system_prompt=(
        "You are a bug hunter specializing in finding defects. "
        "Analyze code systematically for logic errors, edge cases, "
        "resource leaks, and incorrect assumptions. "
        "Reproduce bugs when possible and suggest fixes."
    ),
    tools=["read_file", "search_code", "run_command", "run_tests", "python_executor"],
    max_turns=20,
)

TESTER_ROLE = HGJRole(
    name="tester",
    description="Writes and runs tests to verify functionality",
    system_prompt=(
        "You are a QA engineer focused on test automation. "
        "Write comprehensive tests covering happy paths, edge cases, "
        "and error conditions. Aim for high code coverage."
    ),
    tools=["read_file", "write_file", "run_tests", "run_command"],
    max_turns=20,
)

ARCHITECT_ROLE = HGJRole(
    name="architect",
    description="Designs system architecture and reviews technical decisions",
    system_prompt=(
        "You are a software architect. "
        "Focus on system design, module boundaries, and scalability. "
        "Evaluate trade-offs between different approaches. "
        "Ensure architectural consistency and separation of concerns."
    ),
    tools=["read_file", "search_code", "list_directory"],
    max_turns=15,
)


# Registry of all standard HGJ roles
STANDARD_ROLES: dict[str, HGJRole] = {
    role.name: role
    for role in [DEVELOPER_ROLE, CODE_REVIEWER_ROLE, BUG_HUNTER_ROLE, TESTER_ROLE, ARCHITECT_ROLE]
}


class RoleManager:
    """Manage HGJ roles and their integration with HGJ-dev.

    Provides role lookup, customization, and conversion to
    system prompt format.
    """

    def __init__(self) -> None:
        """Initialize with standard role definitions."""
        self._roles: dict[str, HGJRole] = dict(STANDARD_ROLES)

    def get_role(self, name: str) -> HGJRole | None:
        """Look up a role by name.

        Args:
            name: Role identifier.

        Returns:
            HGJRole if found, None otherwise.
        """
        return self._roles.get(name)

    def register_role(self, role: HGJRole) -> None:
        """Register a custom role.

        Args:
            role: The role to register.
        """
        self._roles[role.name] = role

    def list_roles(self) -> list[str]:
        """Get names of all registered roles.

        Returns:
            List of role names.
        """
        return list(self._roles.keys())

    def to_system_prompt(self, role_name: str) -> str:
        """Convert a role to a system prompt string.

        Args:
            role_name: Role identifier.

        Returns:
            System prompt string for the role.

        Raises:
            ValueError: If role is not found.
        """
        role = self.get_role(role_name)
        if role is None:
            raise ValueError(f"Unknown role: {role_name}")
        return role.system_prompt
