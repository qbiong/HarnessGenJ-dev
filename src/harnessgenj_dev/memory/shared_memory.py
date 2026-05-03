"""Shared memory (Old Gen equivalent).

Cross-role shared storage containing:
- Team member list and role descriptions
- Shared project knowledge
- Cross-role communication artifacts
- Persistent facts and decisions
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from .base import Memory, MemoryEntry

# Standard team composition
TEAM_MEMBERS = {
    "project_manager": "Project Manager — Team coordination, task dispatching, workflow orchestration",
    "product_manager": "Product Manager — Requirements analysis, user stories, feature prioritization",
    "developer": "Developer — Code implementation, bug fixes, feature development",
    "code_reviewer": "Code Reviewer — Code quality, security, best practices review",
    "bug_hunter": "Bug Hunter — Defect diagnosis, root cause analysis",
    "architect": "Architect — System design, module boundaries, scalability",
    "doc_writer": "Doc Writer — Documentation, tutorials, API docs",
}


class SharedMemory(Memory):
    """Cross-role shared memory store.

    All roles can read and write to shared memory.
    Used for team awareness, shared knowledge, and persistent facts.
    """

    def __init__(self, data_dir: str | Path | None = None) -> None:
        super().__init__()
        self._data_dir = data_dir or Path.cwd() / ".hgj-dev" / "memory" / "shared"
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._load()

        # Inject team info if not present
        if not self.get("_team_members"):
            self._inject_team_info()

    def _file(self) -> Path:
        return self._data_dir / "shared_memory.json"

    def _load(self) -> None:
        path = self._file()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                self.from_dict(data)
            except Exception:
                pass

    def save(self) -> None:
        """Persist shared memory to disk."""
        path = self._file()
        data = self.to_dict()
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _inject_team_info(self) -> None:
        """Set up team awareness entries."""
        team_list = "\n".join(
            f"- **@{role}**: {desc}" for role, desc in TEAM_MEMBERS.items()
        )
        self.put(MemoryEntry(
            key="_team_members",
            content=f"## Team Members\n{team_list}",
            tags=["team", "roles"],
        ))
        self.put(MemoryEntry(
            key="_team_collaboration",
            content=(
                "## Team Collaboration\n"
                "Use @mention syntax to assign tasks to team members.\n"
                "Role aliases: @dev -> @developer, @pm -> @product_manager, "
                "@reviewer -> @code_reviewer, @arch -> @architect, @docs -> @doc_writer, "
                "@hunter -> @bug_hunter\n"
                "Parallel execution: multiple @mentions run concurrently.\n"
                "Each role has its own isolated memory (role memory) plus access to this shared memory."
            ),
            tags=["team", "collaboration"],
        ))
        self.save()

    def get_team_block(self) -> str:
        """Get formatted team awareness block for system prompt injection."""
        parts = []
        for key in ["_team_members", "_team_collaboration"]:
            entry = self.get(key)
            if entry:
                parts.append(entry.content)
        return "\n\n".join(parts)

    def get_shared_knowledge(self) -> str:
        """Get formatted shared knowledge for system prompt injection."""
        entries = self.search(tags=["knowledge"])
        if not entries:
            return ""
        lines = ["## Shared Project Knowledge"]
        for e in sorted(entries, key=lambda x: x.access_count, reverse=True):
            lines.append(f"- **{e.key}**: {e.content}")
        return "\n".join(lines)

    def add_shared_knowledge(self, key: str, content: str, tags: list[str] | None = None) -> None:
        """Add or update shared knowledge.

        Args:
            key: Unique key for this knowledge.
            content: The knowledge content.
            tags: Optional additional tags.
        """
        entry_tags = ["knowledge"] + (tags or [])
        self.put(MemoryEntry(
            key=key,
            content=content,
            tags=entry_tags,
        ))
        self.save()

    def add_decision(self, key: str, decision: str, reason: str = "") -> None:
        """Record a team decision in shared memory."""
        content = f"**Decision**: {decision}"
        if reason:
            content += f"\n**Reason**: {reason}"
        content += f"\n**Timestamp**: {time.strftime('%Y-%m-%d %H:%M:%S')}"
        self.put(MemoryEntry(
            key=f"decision_{key}",
            content=content,
            tags=["knowledge", "decision"],
        ))
        self.save()

    def get_member_list(self) -> str:
        """Get list of team member names."""
        entry = self.get("_team_members")
        if not entry:
            return ", ".join(TEAM_MEMBERS.keys())
        return "\n".join(TEAM_MEMBERS.keys())

    @staticmethod
    def get_team_aliases() -> dict[str, str]:
        """Return mapping of aliases to canonical role names."""
        return {
            "dev": "developer",
            "pm": "product_manager",
            "reviewer": "code_reviewer",
            "arch": "architect",
            "docs": "doc_writer",
            "hunter": "bug_hunter",
            "review": "code_reviewer",
            "doc": "doc_writer",
        }
