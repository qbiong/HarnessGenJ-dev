"""Session Manager — per-project conversation session storage.

OpenClaw-inspired design:
- Each project has its own session directory
- Sessions are JSON files with conversation history + metadata
- Sessions support: create, load, list, switch, delete
- Auto-save after each conversation turn
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_SESSIONS_DIR: Path = Path.home() / ".hgj-dev" / "sessions"


@dataclass
class Session:
    """A single conversation session.

    Mirrors OpenClaw session model:
    - id: unique session identifier
    - project: parent project name
    - role: default agent role for this session
    - messages: conversation history (OpenClaw chat.send format)
    - metadata: timestamps, iteration count, etc.
    - checkpoints: P3-4 - saved states for rollback
    """

    id: str
    project: str
    role: str = "product_manager"
    messages: list[dict[str, str]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    checkpoints: list[dict[str, Any]] = field(default_factory=list)  # P3-4

    @property
    def created_at(self) -> str:
        return self.metadata.get("created_at", "")

    @property
    def updated_at(self) -> str:
        return self.metadata.get("updated_at", "")

    @property
    def message_count(self) -> int:
        return len(self.messages)

    def touch(self) -> None:
        """Update the last-accessed timestamp."""
        self.metadata["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation history."""
        self.messages.append({"role": role, "content": content})
        self.touch()

    def clear(self) -> None:
        """Clear conversation history but keep session metadata."""
        self.messages.clear()
        self.touch()

    def to_dict(self) -> dict[str, Any]:
        """Serialize session to dict for JSON storage."""
        return {
            "id": self.id,
            "project": self.project,
            "role": self.role,
            "messages": self.messages,
            "metadata": self.metadata,
            "checkpoints": self.checkpoints,  # P3-4: Checkpoint support
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Session:
        """Deserialize session from dict."""
        return cls(
            id=data["id"],
            project=data["project"],
            role=data.get("role", "product_manager"),
            messages=data.get("messages", []),
            metadata=data.get("metadata", {}),
            checkpoints=data.get("checkpoints", []),  # P3-4
        )


class SessionManager:
    """Manage per-project conversation sessions.

    Storage layout:
        ~/.hgj-dev/sessions/
            {project_name}/
                {session_id}.json    — individual session
                active.json          — currently active session ID

    Usage:
        mgr = SessionManager()
        session = mgr.create_session("my-project", role="developer")
        session.add_message("user", "Hello")
        mgr.save(session)
        sessions = mgr.list_sessions("my-project")
    """

    def __init__(self, base_dir: str | Path | None = None) -> None:
        self._base_dir = Path(base_dir) if base_dir else _SESSIONS_DIR
        self._base_dir.mkdir(parents=True, exist_ok=True)
        # In-memory cache: project -> {session_id -> Session}
        self._cache: dict[str, dict[str, Session]] = {}

    def _project_dir(self, project: str) -> Path:
        """Get the directory for a project's sessions."""
        safe_name = project.replace("/", "_").replace("\\", "_")
        return self._base_dir / safe_name

    def _session_file(self, project: str, session_id: str) -> Path:
        """Get the file path for a session."""
        return self._project_dir(project) / f"{session_id}.json"

    def _active_file(self, project: str) -> Path:
        """Get the file path for the active session ID."""
        return self._project_dir(project) / "active.json"

    def _load_project_cache(self, project: str) -> dict[str, Session]:
        """Load all sessions for a project into memory cache."""
        if project in self._cache:
            return self._cache[project]

        project_dir = self._project_dir(project)
        project_dir.mkdir(parents=True, exist_ok=True)

        sessions = {}
        for f in project_dir.glob("*.json"):
            if f.name == "active.json":
                continue
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                session = Session.from_dict(data)
                sessions[session.id] = session
            except Exception:
                pass

        self._cache[project] = sessions
        return sessions

    def create_session(
        self, project: str, role: str = "product_manager"
    ) -> Session:
        """Create a new session for a project.

        Args:
            project: Project name.
            role: Default agent role.

        Returns:
            New Session instance.
        """
        session_id = str(uuid.uuid4())[:8]
        now = time.strftime("%Y-%m-%dT%H:%M:%S")

        session = Session(
            id=session_id,
            project=project,
            role=role,
            messages=[],
            metadata={
                "created_at": now,
                "updated_at": now,
                "iterations": 0,
            },
        )

        self._save_session(session)
        self._set_active(project, session_id)
        return session

    def get_session(self, project: str, session_id: str) -> Session | None:
        """Get a session by project and ID.

        Args:
            project: Project name.
            session_id: Session ID.

        Returns:
            Session instance or None if not found.
        """
        cache = self._load_project_cache(project)
        if session_id in cache:
            return cache[session_id]

        # Try loading from disk
        fpath = self._session_file(project, session_id)
        if fpath.exists():
            try:
                data = json.loads(fpath.read_text(encoding="utf-8"))
                session = Session.from_dict(data)
                cache[session_id] = session
                return session
            except Exception:
                pass
        return None

    def get_active_session(self, project: str, create: bool = True) -> Session | None:
        """Get the currently active session for a project.

        Args:
            project: Project name.
            create: If True and no active session, create one.

        Returns:
            Active Session instance or None.
        """
        active_id = self._get_active(project)
        if active_id:
            session = self.get_session(project, active_id)
            if session:
                return session
        if not create:
            return None
        return self.create_session(project)

    def list_sessions(
        self, project: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        """List all sessions for a project, sorted by last updated.

        Args:
            project: Project name.
            limit: Maximum number of sessions to return.

        Returns:
            List of session summary dicts (id, role, created_at, updated_at, message_count).
        """
        cache = self._load_project_cache(project)
        active_id = self._get_active(project)

        sessions = []
        for s in cache.values():
            sessions.append(
                {
                    "id": s.id,
                    "role": s.role,
                    "created_at": s.created_at,
                    "updated_at": s.updated_at,
                    "message_count": s.message_count,
                    "active": s.id == active_id,
                    "title": self._session_title(s),
                }
            )

        sessions.sort(key=lambda x: x["updated_at"], reverse=True)
        return sessions[:limit]

    def delete_session(self, project: str, session_id: str) -> bool:
        """Delete a session.

        Args:
            project: Project name.
            session_id: Session ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        cache = self._load_project_cache(project)
        if session_id not in cache:
            return False

        # Remove from cache
        del cache[session_id]

        # Remove from disk
        fpath = self._session_file(project, session_id)
        fpath.unlink(missing_ok=True)

        # If this was the active session, clear active marker
        active_id = self._get_active(project)
        if active_id == session_id:
            self._active_file(project).unlink(missing_ok=True)
            # Don't auto-create a new session — let caller decide

        return True

    def fork_session(
        self, project: str, session_id: str, new_role: str | None = None
    ) -> Session | None:
        """Fork a session to create a new branch.

        Creates a new session with copied conversation history.
        The original session remains unchanged.

        Args:
            project: Project name.
            session_id: Session ID to fork from.
            new_role: Optional new role for the forked session.

        Returns:
            New forked Session or None if source not found.
        """
        original = self.get_session(project, session_id)
        if original is None:
            return None

        # Create new session
        forked = self.create_session(project, role=new_role or original.role)

        # Copy messages from original
        forked.messages = original.messages.copy()

        # Copy metadata with fork info
        forked.metadata = {
            **original.metadata,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "forked_from": session_id,
        }

        self._save_session(forked)
        return forked

    def get_fork_tree(
        self, project: str, session_id: str
    ) -> list[dict[str, Any]]:
        """Get the fork tree for a session (all forks descendants).

        Args:
            project: Project name.
            session_id: Root session ID.

        Returns:
            List of sessions in the fork tree.
        """
        cache = self._load_project_cache(project)

        # Build fork tree using BFS
        tree = []
        queue = [session_id]
        visited = set()

        while queue:
            sid = queue.pop(0)
            if sid in visited:
                continue
            visited.add(sid)

            session = cache.get(sid)
            if session:
                tree.append({
                    "id": session.id,
                    "role": session.role,
                    "created_at": session.created_at,
                    "forked_from": session.metadata.get("forked_from"),
                })
                # Add children (sessions forked from this one)
                for other in cache.values():
                    if other.metadata.get("forked_from") == sid:
                        queue.append(other.id)

        return tree

    def switch_session(self, project: str, session_id: str) -> bool:
        """Switch the active session for a project.

        Args:
            project: Project name.
            session_id: Session ID to switch to.

        Returns:
            True if session exists and switched, False otherwise.
        """
        session = self.get_session(project, session_id)
        if session is None:
            return False
        self._set_active(project, session_id)
        return True

    def save(self, session: Session) -> None:
        """Save a session to disk.

        Args:
            session: Session instance to save.
        """
        self._save_session(session)

    def _save_session(self, session: Session) -> None:
        """Internal: persist session to disk."""
        project_dir = self._project_dir(session.project)
        project_dir.mkdir(parents=True, exist_ok=True)

        fpath = self._session_file(session.project, session.id)
        data = session.to_dict()
        fpath.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        # Update cache
        cache = self._load_project_cache(session.project)
        cache[session.id] = session

    def create_checkpoint(
        self, project: str, session_id: str, label: str = ""
    ) -> str | None:
        """Create a checkpoint of the current session state.

        Args:
            project: Project name.
            session_id: Session ID.
            label: Optional label for this checkpoint.

        Returns:
            Checkpoint ID if created, None if session not found.
        """
        session = self.get_session(project, session_id)
        if not session:
            return None

        import uuid

        checkpoint_id = str(uuid.uuid4())[:8]
        checkpoint = {
            "id": checkpoint_id,
            "label": label or f"Checkpoint {len(session.checkpoints) + 1}",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "message_count": len(session.messages),
            "messages": session.messages.copy(),  # Deep copy
        }

        session.checkpoints.append(checkpoint)
        self._save_session(session)
        return checkpoint_id

    def rollback_to_checkpoint(
        self, project: str, session_id: str, checkpoint_id: str
    ) -> bool:
        """Rollback session to a previous checkpoint.

        Args:
            project: Project name.
            session_id: Session ID.
            checkpoint_id: Checkpoint ID to rollback to.

        Returns:
            True if rollback successful, False otherwise.
        """
        session = self.get_session(project, session_id)
        if not session:
            return False

        # Find checkpoint
        checkpoint = None
        for cp in session.checkpoints:
            if cp["id"] == checkpoint_id:
                checkpoint = cp
                break

        if not checkpoint:
            return False

        # Restore messages from checkpoint
        session.messages = checkpoint["messages"].copy()
        session.metadata["rolled_back_from"] = checkpoint_id
        session.metadata["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        self._save_session(session)
        return True

    def list_checkpoints(self, project: str, session_id: str) -> list[dict[str, Any]]:
        """List all checkpoints for a session.

        Args:
            project: Project name.
            session_id: Session ID.

        Returns:
            List of checkpoint summaries.
        """
        session = self.get_session(project, session_id)
        if not session:
            return []

        return [
            {
                "id": cp["id"],
                "label": cp["label"],
                "created_at": cp["created_at"],
                "message_count": cp["message_count"],
            }
            for cp in session.checkpoints
        ]

    def _get_active(self, project: str) -> str | None:
        """Get the active session ID for a project."""
        fpath = self._active_file(project)
        if fpath.exists():
            try:
                data = json.loads(fpath.read_text(encoding="utf-8"))
                return data.get("session_id")
            except Exception:
                pass
        return None

    def _set_active(self, project: str, session_id: str) -> None:
        """Set the active session ID for a project."""
        fpath = self._active_file(project)
        fpath.parent.mkdir(parents=True, exist_ok=True)
        fpath.write_text(
            json.dumps({"session_id": session_id}, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _session_title(session: Session) -> str:
        """Generate a title from the first user message."""
        for msg in session.messages:
            if msg.get("role") == "user":
                content = msg.get("content", "").strip()
                return content[:80] + ("..." if len(content) > 80 else "")
        return "New conversation"
