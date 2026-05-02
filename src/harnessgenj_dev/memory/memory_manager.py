"""Memory Manager — coordinates role memory and shared memory.

JVM-inspired architecture:
- Role Memory = Young Gen (per-role, isolated, short-lived context)
- Shared Memory = Old Gen (cross-role, shared, long-lived knowledge)
- Memory Manager = GC Coordinator (manages loading, saving, prompt assembly)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .role_memory import RoleMemory
from .shared_memory import SharedMemory


class MemoryManager:
    """Coordinate role-specific and shared memory for all team roles.

    Usage:
        mgr = MemoryManager(data_dir=".hgj-dev/memory")
        prompt = mgr.build_prompt("developer")
        mgr.save_all()
    """

    def __init__(self, data_dir: str | Path | None = None) -> None:
        self._data_dir = Path(data_dir) if data_dir else Path.cwd() / ".hgj-dev" / "memory"
        self._role_memories: dict[str, RoleMemory] = {}
        self._shared = SharedMemory(data_dir=self._data_dir / "shared")

    def get_role_memory(self, role: str) -> RoleMemory:
        """Get or create role memory for a given role.

        Args:
            role: Role name (e.g., 'developer', 'product_manager').

        Returns:
            RoleMemory instance for the role.
        """
        if role not in self._role_memories:
            self._role_memories[role] = RoleMemory(
                role=role,
                data_dir=self._data_dir / role,
            )
        return self._role_memories[role]

    @property
    def shared(self) -> SharedMemory:
        """Access shared memory."""
        return self._shared

    def build_prompt(self, role: str) -> str:
        """Build memory block for injection into system prompt.

        Combines:
        1. Role identity & responsibilities (from role memory)
        2. Team awareness (from shared memory)
        3. Shared knowledge (from shared memory)
        4. Role-specific knowledge (from role memory)

        Args:
            role: Role name.

        Returns:
            Formatted memory block for system prompt.
        """
        role_mem = self.get_role_memory(role)
        parts = []

        # 1. Role identity
        identity = role_mem.get_identity_block()
        if identity:
            parts.append(identity)

        # 2. Team awareness
        team = self._shared.get_team_block()
        if team:
            parts.append(team)

        # 3. Shared knowledge
        shared_knowledge = self._shared.get_shared_knowledge()
        if shared_knowledge:
            parts.append(shared_knowledge)

        # 4. Role-specific knowledge
        role_knowledge = role_mem.get_knowledge_block()
        if role_knowledge:
            parts.append(role_knowledge)

        # 5. Memory awareness instruction
        parts.append(
            "## Memory\n"
            "You have access to role-specific memory (isolated to your role) "
            "and shared memory (accessible by all team members).\n"
            "Your role identity, responsibilities, and team member information "
            "are stored in memory and define who you are.\n"
            "Use this context to inform your responses and decisions."
        )

        return "\n\n".join(parts)

    def save_all(self) -> None:
        """Persist all memory to disk."""
        self._shared.save()
        for role_mem in self._role_memories.values():
            role_mem.save()

    def get_role_info(self) -> dict[str, dict[str, Any]]:
        """Get summary info about all loaded role memories."""
        info = {}
        for role, mem in self._role_memories.items():
            info[role] = {
                "entries": mem.count(),
                "keys": mem.keys(),
            }
        return info

    def reset_role(self, role: str) -> None:
        """Clear and reinitialize a role's memory."""
        if role in self._role_memories:
            self._role_memories[role].clear()
            self._role_memories[role]._inject_identity()
            self._role_memories[role].save()

    def reset_all(self) -> None:
        """Clear all memory."""
        self._shared.clear()
        self._shared._inject_team_info()
        self._shared.save()
        for role, mem in self._role_memories.items():
            mem.clear()
            mem._inject_identity()
            mem.save()
