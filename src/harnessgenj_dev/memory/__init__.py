"""Memory system for role isolation and shared knowledge.

JVM-inspired architecture:
- RoleMemory (Young Gen): Per-role, isolated, short-lived
- SharedMemory (Old Gen): Cross-role, shared, long-lived
- MemoryManager: Coordinates loading, saving, prompt assembly
"""

from .base import Memory, MemoryEntry
from .memory_manager import MemoryManager
from .role_memory import RoleMemory
from .shared_memory import TEAM_MEMBERS, SharedMemory

__all__ = [
    "Memory",
    "MemoryEntry",
    "RoleMemory",
    "SharedMemory",
    "TEAM_MEMBERS",
    "MemoryManager",
]
