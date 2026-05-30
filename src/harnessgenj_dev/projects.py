"""Multi-project management for HarnessGenJ-dev."""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Framework workspace directory for user projects (relative to project root)
_WORKSPACE_DIR: Path = Path(__file__).resolve().parent.parent.parent / "workspace"


@dataclass
class Project:
    """A managed project."""

    name: str
    path: str
    description: str = ""
    github_url: str = ""
    is_external: bool = False
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        self.last_accessed = time.time()


class ProjectManager:
    """Manage multiple projects with switching and context isolation."""

    def __init__(self, storage_path: Path | str | None = None) -> None:
        self._projects: dict[str, Project] = {}
        self._active_project: str | None = None
        self._storage_path = Path(storage_path) if storage_path else None

    @staticmethod
    def get_workspace_dir() -> Path:
        """Get the default workspace directory for new projects."""
        _WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
        return _WORKSPACE_DIR

    def add_project(
        self,
        name: str,
        path: str | Path | None = None,
        description: str = "",
        github_url: str = "",
        is_external: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> Project:
        """Register a new project. Creates directory if it doesn't exist.

        Args:
            name: Project identifier.
            path: Filesystem path. If None, auto-creates under workspace/<name>.
            description: Human-readable description.
            github_url: GitHub repository URL (optional).
            is_external: True if this is an existing external project.
            metadata: Optional extra metadata.
        """
        if path:
            resolved = Path(path)
            is_external = True  # user provided path = external project
        else:
            resolved = self.get_workspace_dir() / name
            is_external = False

        # Create directory if it doesn't exist
        resolved.mkdir(parents=True, exist_ok=True)
        logger.info("Created project dir: %s", resolved)

        project = Project(
            name=name,
            path=str(resolved.resolve()),
            description=description,
            github_url=github_url,
            is_external=is_external,
            metadata=metadata or {},
        )
        self._projects[name] = project
        self._save()
        return project

    def remove_project(self, name: str) -> bool:
        if name in self._projects:
            del self._projects[name]
            if self._active_project == name:
                self._active_project = None
            self._save()
            return True
        return False

    def switch_to(self, name: str) -> Project:
        if name not in self._projects:
            raise KeyError(f"Project '{name}' not found")
        self._active_project = name
        self._projects[name].touch()
        self._save()
        return self._projects[name]

    def get_active(self) -> Project | None:
        if self._active_project:
            return self._projects.get(self._active_project)
        return None

    def get_project(self, name: str) -> Project | None:
        return self._projects.get(name)

    def list_projects(self) -> list[Project]:
        return sorted(self._projects.values(), key=lambda p: p.last_accessed, reverse=True)

    def update_description(self, name: str, description: str) -> bool:
        """Update project description (e.g. AI-generated)."""
        if name in self._projects:
            self._projects[name].description = description
            self._save()
            return True
        return False

    @property
    def active_name(self) -> str | None:
        return self._active_project

    @property
    def project_count(self) -> int:
        return len(self._projects)

    def _save(self) -> None:
        if self._storage_path is None:
            return
        data = {}
        for name, p in self._projects.items():
            data[name] = {
                "name": p.name,
                "path": p.path,
                "description": p.description,
                "github_url": p.github_url,
                "is_external": p.is_external,
                "created_at": p.created_at,
                "last_accessed": p.last_accessed,
                "metadata": p.metadata,
            }
        data["_active"] = self._active_project
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load(self) -> None:
        if self._storage_path is None or not self._storage_path.exists():
            return
        with open(self._storage_path, encoding="utf-8") as f:
            data = json.load(f)
        self._active_project = data.pop("_active", None)
        for name, info in data.items():
            self._projects[name] = Project(
                name=info["name"],
                path=info["path"],
                description=info.get("description", ""),
                github_url=info.get("github_url", ""),
                is_external=info.get("is_external", True),
                created_at=info.get("created_at", time.time()),
                last_accessed=info.get("last_accessed", time.time()),
                metadata=info.get("metadata", {}),
            )


# Module-level singleton
_mgr = ProjectManager(storage_path=Path.home() / ".hgj-dev" / "projects.json")
_mgr.load()


def get_projects() -> list[dict[str, Any]]:
    return [
        {
            "name": p.name,
            "path": p.path,
            "description": p.description,
            "github_url": p.github_url,
            "is_external": p.is_external,
            "active": _mgr._active_project == p.name,
        }
        for p in _mgr._projects.values()
    ]


def get_active_project() -> dict[str, Any] | None:
    p = _mgr.get_active()
    if p:
        return {
            "name": p.name,
            "path": p.path,
            "description": p.description,
            "github_url": p.github_url,
            "is_external": p.is_external,
            "active": True,
        }
    return None


def add_project(
    name: str,
    path: str | None = None,
    description: str = "",
    github_url: str = "",
) -> Project:
    """Register a new project. If path is None, creates under workspace/<name>."""
    return _mgr.add_project(name=name, path=path or None, description=description, github_url=github_url)


def add_external_project(name: str, path: str, description: str = "", github_url: str = "") -> Project:
    """Register an existing external project by path."""
    return _mgr.add_project(name=name, path=path, description=description, github_url=github_url, is_external=True)


def switch_project(name: str) -> Project:
    return _mgr.switch_to(name)


def remove_project(name: str) -> bool:
    return _mgr.remove_project(name)


def get_workspace_dir() -> str:
    return str(_mgr.get_workspace_dir())


def update_project_description(name: str, description: str) -> bool:
    return _mgr.update_description(name, description)
