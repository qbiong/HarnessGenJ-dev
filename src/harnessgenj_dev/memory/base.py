"""Memory base classes for role and shared memory.

JVM-inspired architecture:
- Role Memory (Young Gen): Per-role, short-lived, isolated
- Shared Memory (Old Gen): Cross-role, long-lived, shared
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MemoryEntry:
    """A single memory entry with metadata.

    Attributes:
        key: Unique identifier for this memory.
        content: The actual memory content.
        tags: Tags for categorization and retrieval.
        created_at: Unix timestamp when created.
        access_count: Number of times accessed.
        role: Role that owns this memory (empty for shared).
    """

    key: str
    content: str
    tags: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    access_count: int = 0
    role: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "content": self.content,
            "tags": self.tags,
            "created_at": self.created_at,
            "access_count": self.access_count,
            "role": self.role,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryEntry:
        return cls(
            key=data["key"],
            content=data["content"],
            tags=data.get("tags", []),
            created_at=data.get("created_at", time.time()),
            access_count=data.get("access_count", 0),
            role=data.get("role", ""),
        )


class Memory:
    """Abstract memory store with CRUD operations.

    Subclasses implement persistence (in-memory or file-based).
    """

    def __init__(self) -> None:
        self._entries: dict[str, MemoryEntry] = {}

    def put(self, entry: MemoryEntry) -> None:
        """Store a memory entry."""
        self._entries[entry.key] = entry

    def get(self, key: str) -> MemoryEntry | None:
        """Retrieve a memory entry by key."""
        entry = self._entries.get(key)
        if entry:
            entry.access_count += 1
        return entry

    def delete(self, key: str) -> bool:
        """Remove a memory entry."""
        return self._entries.pop(key, None) is not None

    def search(self, tags: list[str] | None = None) -> list[MemoryEntry]:
        """Search memories by tags.

        Args:
            tags: Tags to match. None returns all entries.

        Returns:
            List of matching entries.
        """
        if tags is None:
            return list(self._entries.values())
        return [
            e for e in self._entries.values()
            if any(t in e.tags for t in tags)
        ]

    def keys(self) -> list[str]:
        """Return all memory keys."""
        return list(self._entries.keys())

    def clear(self) -> None:
        """Remove all entries."""
        self._entries.clear()

    def count(self) -> int:
        """Return number of entries."""
        return len(self._entries)

    def to_dict(self) -> dict[str, dict[str, Any]]:
        return {k: v.to_dict() for k, v in self._entries.items()}

    def from_dict(self, data: dict[str, dict[str, Any]]) -> None:
        self._entries.clear()
        for key, d in data.items():
            self._entries[key] = MemoryEntry.from_dict(d)
