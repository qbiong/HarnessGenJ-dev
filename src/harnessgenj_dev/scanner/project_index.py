"""Project index and file tree builder."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FileNode:
    """A node in the file tree."""

    name: str
    is_directory: bool
    path: str
    children: list[FileNode] = field(default_factory=list)
    language: str = ""


class ProjectIndex:
    """Build and maintain a project file tree index."""

    DEFAULT_IGNORE = {
        ".git",
        ".hg",
        ".svn",
        "__pycache__",
        "node_modules",
        ".venv",
        "venv",
        ".mypy_cache",
        ".pytest_cache",
        ".claude",
        ".spec-workflow",
    }

    def __init__(self, root: str = ".") -> None:
        self.root = Path(root)
        self.tree: FileNode | None = None
        self.file_count = 0

    def scan(self, max_depth: int = 10) -> FileNode:
        """Scan the project directory and build the file tree."""
        self.tree = self._build_tree(self.root, max_depth, 0)
        return self.tree

    def _build_tree(self, path: Path, max_depth: int, current_depth: int) -> FileNode:
        """Recursively build the file tree."""
        if current_depth >= max_depth:
            return FileNode(name=path.name, is_directory=True, path=str(path))

        node = FileNode(name=path.name, is_directory=path.is_dir(), path=str(path))

        if path.is_dir():
            try:
                items = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name))
            except PermissionError:
                return node

            for item in items:
                if item.name in self.DEFAULT_IGNORE or item.name.startswith("."):
                    continue
                child = self._build_tree(item, max_depth, current_depth + 1)
                node.children.append(child)
                if not child.is_directory:
                    self.file_count += 1
                    child.language = self._detect_language(item)

        return node

    def _detect_language(self, path: Path) -> str:
        """Detect the programming language from file extension."""
        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".go": "go",
            ".rs": "rust",
            ".java": "java",
            ".c": "c",
            ".cpp": "cpp",
            ".h": "c",
            ".hpp": "cpp",
            ".rb": "ruby",
            ".rs": "rust",
            ".md": "markdown",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".json": "json",
            ".toml": "toml",
        }
        return ext_map.get(path.suffix, "unknown")

    def get_file_tree_string(self, node: FileNode | None = None, prefix: str = "") -> str:
        """Get a human-readable file tree string."""
        if node is None:
            node = self.tree
        if node is None:
            return "(no tree - run scan() first)"

        result = f"{prefix}{node.name}/\n" if node.is_directory else f"{prefix}{node.name}\n"
        children = [c for c in (node.children or [])]
        for i, child in enumerate(children):
            connector = "├── " if i < len(children) - 1 else "└── "
            extension = "│   " if i < len(children) - 1 else "    "
            result += f"{prefix}{connector}"
            result += self.get_file_tree_string(child, prefix + extension).lstrip()
        return result
