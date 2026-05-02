"""Code search - ripgrep wrapper with symbol search and highlighting.

Provides fast full-text code search using ripgrep (rg) as the backend,
with a Python regex fallback. Also supports symbol-level search
by integrating with the SymbolTable.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class SearchResult:
    """A single search result match."""

    file_path: str
    line_number: int
    line_content: str
    match_start: int = 0
    match_end: int = 0

    def highlighted(self, max_context: int = 40) -> str:
        """Return the matched portion of the line with context.

        Args:
            max_context: Characters of context around the match.

        Returns:
            Highlighted match string.
        """
        start = max(0, self.match_start - max_context)
        end = min(len(self.line_content), self.match_end + max_context)
        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(self.line_content) else ""
        return f"{prefix}{self.line_content[start:end]}{suffix}"


class CodeSearch:
    """Fast code search using ripgrep with Python regex fallback.

    Supports full-text search, file filtering, and symbol search
    via integration with SymbolTable.
    """

    CODE_EXTENSIONS = {
        ".py", ".js", ".ts", ".tsx", ".jsx",
        ".go", ".rs", ".java", ".c", ".cpp", ".h", ".hpp",
        ".rb", ".php", ".swift", ".kt", ".scala",
        ".sh", ".bash", ".zsh",
        ".yaml", ".yml", ".json", ".toml", ".md",
        ".sql", ".css", ".scss", ".html",
    }

    def __init__(self, root_path: str | Path = ".") -> None:
        """Initialize code search.

        Args:
            root_path: Project root directory.
        """
        self.root_path = Path(root_path).resolve()
        self._has_rg = self._check_rg()

    def _check_rg(self) -> bool:
        """Check if ripgrep is available."""
        try:
            result = subprocess.run(
                ["rg", "--version"],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def search(
        self,
        pattern: str,
        path: str | None = None,
        case_sensitive: bool = False,
        word: bool = False,
        context_lines: int = 0,
        file_type: str | None = None,
        max_results: int = 100,
    ) -> list[SearchResult]:
        """Search for pattern in code files.

        Args:
            pattern: Search pattern (regex if ripgrep available, else Python regex).
            path: Subdirectory to search in (relative to root).
            case_sensitive: Whether to do case-sensitive search.
            word: Match whole words only.
            context_lines: Number of context lines (not used in basic mode).
            file_type: Filter by file extension (e.g., ".py").
            max_results: Maximum number of results to return.

        Returns:
            List of SearchResult objects.
        """
        if self._has_rg:
            return self._search_rg(
                pattern, path, case_sensitive, word, file_type, max_results
            )
        return self._search_python(
            pattern, path, case_sensitive, word, file_type, max_results
        )

    def _search_rg(
        self,
        pattern: str,
        path: str | None,
        case_sensitive: bool,
        word: bool,
        file_type: str | None,
        max_results: int,
    ) -> list[SearchResult]:
        """Search using ripgrep."""
        search_path = str(self.root_path / path) if path else str(self.root_path)

        cmd = ["rg", "--json", "--no-heading", "--line-number"]

        if not case_sensitive:
            cmd.append("-i")
        if word:
            cmd.append("-w")
        if file_type:
            cmd.extend(["-g", f"*{file_type}"])

        cmd.extend([pattern, search_path])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            return []

        results = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            try:
                import json
                entry = json.loads(line)
                if entry.get("type") != "match":
                    continue
                data = entry["data"]
                results.append(SearchResult(
                    file_path=data["path"]["text"],
                    line_number=data["line_number"],
                    line_content=data["lines"]["text"].rstrip(),
                    match_start=data.get("submatches", [{}])[0].get("start", 0),
                    match_end=data.get("submatches", [{}])[0].get("end", 0),
                ))
            except (json.JSONDecodeError, KeyError, IndexError):
                continue

            if len(results) >= max_results:
                break

        return results

    def _search_python(
        self,
        pattern: str,
        path: str | None,
        case_sensitive: bool,
        word: bool,
        file_type: str | None,
        max_results: int,
    ) -> list[SearchResult]:
        """Search using Python regex (ripgrep fallback)."""
        search_path = self.root_path / path if path else self.root_path
        flags = 0 if case_sensitive else re.IGNORECASE
        if word:
            pattern = rf"\b{re.escape(pattern)}\b"

        try:
            regex = re.compile(pattern, flags)
        except re.error:
            return []

        results = []
        for ext in self.CODE_EXTENSIONS:
            if file_type and ext != file_type:
                continue
            for file_path in search_path.rglob(f"*{ext}"):
                # Skip hidden directories
                if any(part.startswith(".") for part in file_path.parts):
                    continue
                try:
                    with open(file_path, encoding="utf-8") as f:
                        for line_num, line in enumerate(f, 1):
                            match = regex.search(line)
                            if match:
                                results.append(SearchResult(
                                    file_path=str(file_path),
                                    line_number=line_num,
                                    line_content=line.rstrip(),
                                    match_start=match.start(),
                                    match_end=match.end(),
                                ))
                                if len(results) >= max_results:
                                    return results
                except (UnicodeDecodeError, PermissionError, OSError):
                    continue

        return results

    def search_symbol(
        self,
        symbol_name: str,
        symbol_table: Any | None = None,
    ) -> list[SearchResult]:
        """Search for a symbol by name across all files.

        If a SymbolTable is provided, uses it for fast lookup.
        Otherwise falls back to full-text search.

        Args:
            symbol_name: Symbol name to search for.
            symbol_table: Optional SymbolTable for indexed search.

        Returns:
            List of SearchResult objects.
        """
        if symbol_table is not None:
            # Use indexed search
            symbols = symbol_table.lookup_by_name(symbol_name)
            results = []
            for sym in symbols:
                results.append(SearchResult(
                    file_path=sym.file_path,
                    line_number=sym.line_start,
                    line_content=f"{sym.kind}: {sym.name}",
                    match_start=0,
                    match_end=len(sym.name),
                ))
            return results

        # Fallback: full-text search
        return self.search(
            rf"\b{re.escape(symbol_name)}\b",
            word=True,
            max_results=50,
        )
