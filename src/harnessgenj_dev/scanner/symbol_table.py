"""Symbol table - global index of code symbols across a project.

Provides a searchable index of functions, classes, methods, and imports
collected from multiple files. Supports lookup by name, kind, and fuzzy search.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .ast_analyzer import FileAnalysis, PythonASTAnalyzer, SymbolInfo


@dataclass
class SymbolTable:
    """Global symbol index for a project.

    Collects symbols from multiple files and provides search capabilities.
    """

    _symbols: list[SymbolInfo] = field(default_factory=list)
    _files_analyzed: int = 0
    _total_imports: int = 0

    def add_analysis(self, analysis: FileAnalysis) -> None:
        """Add analysis results from a single file.

        Args:
            analysis: FileAnalysis from ASTAnalyzer.
        """
        self._symbols.extend(analysis.symbols)
        self._files_analyzed += 1
        self._total_imports += len(analysis.imports)

    def build_from_directory(
        self,
        dir_path: str | Path,
        exclude_patterns: list[str] | None = None,
    ) -> None:
        """Build symbol table by analyzing all Python files in a directory.

        Args:
            dir_path: Root directory to scan.
            exclude_patterns: Glob patterns to exclude.
        """
        analyzer = PythonASTAnalyzer()
        analyses = analyzer.analyze_directory(dir_path, exclude_patterns)
        for analysis in analyses:
            self.add_analysis(analysis)

    def lookup_by_name(self, name: str) -> list[SymbolInfo]:
        """Find all symbols with the given name.

        Args:
            name: Exact symbol name.

        Returns:
            List of matching SymbolInfo objects.
        """
        return [s for s in self._symbols if s.name == name]

    def lookup_by_kind(self, kind: str) -> list[SymbolInfo]:
        """Find all symbols of a given kind.

        Args:
            kind: Symbol kind ("function", "class", "method", "import").

        Returns:
            List of matching SymbolInfo objects.
        """
        return [s for s in self._symbols if s.kind == kind]

    def lookup_by_file(self, file_path: str) -> list[SymbolInfo]:
        """Find all symbols in a given file.

        Args:
            file_path: File path (substring match).

        Returns:
            List of SymbolInfo objects from that file.
        """
        return [s for s in self._symbols if file_path in s.file_path]

    def search(self, query: str, kind: str | None = None) -> list[SymbolInfo]:
        """Fuzzy search for symbols matching the query.

        Searches in symbol names (case-insensitive substring match).

        Args:
            query: Search query (substring).
            kind: Optional filter by symbol kind.

        Returns:
            List of matching SymbolInfo objects.
        """
        query_lower = query.lower()
        results = [s for s in self._symbols if query_lower in s.name.lower()]
        if kind:
            results = [s for s in results if s.kind == kind]
        return results

    def get_classes(self) -> list[SymbolInfo]:
        """Get all class symbols."""
        return self.lookup_by_kind("class")

    def get_functions(self) -> list[SymbolInfo]:
        """Get all function symbols (excluding methods)."""
        return self.lookup_by_kind("function")

    def get_methods(self) -> list[SymbolInfo]:
        """Get all method symbols."""
        return self.lookup_by_kind("method")

    def get_imports(self) -> list[SymbolInfo]:
        """Get all import symbols."""
        return self.lookup_by_kind("import")

    def summary(self) -> dict[str, Any]:
        """Get summary statistics.

        Returns:
            Dict with counts by kind and file count.
        """
        counts: dict[str, int] = {}
        for s in self._symbols:
            counts[s.kind] = counts.get(s.kind, 0) + 1

        return {
            "files_analyzed": self._files_analyzed,
            "total_symbols": len(self._symbols),
            "total_imports": self._total_imports,
            "by_kind": counts,
        }

    def clear(self) -> None:
        """Clear all symbols."""
        self._symbols.clear()
        self._files_analyzed = 0
        self._total_imports = 0
