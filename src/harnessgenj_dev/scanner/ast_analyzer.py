"""AST analyzer for Python and multi-language code parsing.

Uses Python's built-in ast module for Python files and tree-sitter
for other languages (JavaScript, TypeScript, Go, Rust, etc.).
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SymbolInfo:
    """Information about a code symbol (function, class, variable)."""

    name: str
    kind: str  # "function", "class", "method", "import", "variable"
    file_path: str
    line_start: int
    line_end: int
    docstring: str | None = None
    args: list[str] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)
    parent: str | None = None  # Class name for methods


@dataclass
class FileAnalysis:
    """Result of analyzing a single file."""

    file_path: str
    language: str
    symbols: list[SymbolInfo] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    complexity: int = 0  # Cyclomatic complexity estimate


class PythonASTAnalyzer:
    """Analyze Python files using the built-in ast module.

    Extracts functions, classes, methods, imports, and decorators.
    """

    def analyze_file(self, file_path: str | Path) -> FileAnalysis:
        """Analyze a Python file and extract symbol information.

        Args:
            file_path: Path to the Python file.

        Returns:
            FileAnalysis with symbols, imports, and complexity estimate.
        """
        path = Path(file_path)
        with open(path, encoding="utf-8") as f:
            source = f.read()

        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            return FileAnalysis(
                file_path=str(path),
                language="python",
                symbols=[],
                imports=[],
                complexity=0,
            )

        analyzer = _PythonNodeVisitor(str(path))
        analyzer.visit(tree)

        return FileAnalysis(
            file_path=str(path),
            language="python",
            symbols=analyzer.symbols,
            imports=analyzer.imports,
            complexity=analyzer.complexity,
        )

    def analyze_directory(
        self,
        dir_path: str | Path,
        exclude_patterns: list[str] | None = None,
    ) -> list[FileAnalysis]:
        """Recursively analyze all Python files in a directory.

        Args:
            dir_path: Root directory to scan.
            exclude_patterns: Glob patterns to exclude (e.g., ["test_*", "*_test.py"]).

        Returns:
            List of FileAnalysis results.
        """
        results = []
        exclude = exclude_patterns or []
        root = Path(dir_path)

        for py_file in root.rglob("*.py"):
            # Check exclusions
            if any(py_file.match(pat) for pat in exclude):
                continue
            # Skip hidden directories
            if any(part.startswith(".") for part in py_file.parts):
                continue
            results.append(self.analyze_file(py_file))

        return results


class _PythonNodeVisitor(ast.NodeVisitor):
    """AST visitor that collects symbols, imports, and complexity metrics."""

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        self.symbols: list[SymbolInfo] = []
        self.imports: list[str] = []
        self.complexity = 1  # Base complexity
        self._current_class: str | None = None

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        kind = "method" if self._current_class else "function"
        decorators = [
            self._get_decorator_name(d) for d in node.decorator_list
        ]

        args = []
        for arg in node.args.args:
            if arg.arg != "self":
                args.append(arg.arg)

        docstring = ast.get_docstring(node)

        symbol = SymbolInfo(
            name=node.name,
            kind=kind,
            file_path=self.file_path,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            docstring=docstring,
            args=args,
            decorators=decorators,
            parent=self._current_class,
        )
        self.symbols.append(symbol)

        # Complexity: branches and loops add to complexity
        self.complexity += 1

        # Visit children with current class context
        old_class = self._current_class
        if kind == "function":
            self._current_class = None
        self.generic_visit(node)
        self._current_class = old_class

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        decorators = [
            self._get_decorator_name(d) for d in node.decorator_list
        ]
        symbol = SymbolInfo(
            name=node.name,
            kind="class",
            file_path=self.file_path,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            docstring=ast.get_docstring(node),
            decorators=decorators,
        )
        self.symbols.append(symbol)

        old_class = self._current_class
        self._current_class = node.name
        self.generic_visit(node)
        self._current_class = old_class

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.append(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            for alias in node.names:
                self.imports.append(f"{node.module}.{alias.name}")
        self.generic_visit(node)

    def visit_If(self, node: ast.If) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        # and/or add complexity
        self.complexity += len(node.values) - 1
        self.generic_visit(node)

    def _get_decorator_name(self, node: ast.expr) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        if isinstance(node, ast.Call):
            return self._get_decorator_name(node.func)
        return "unknown"
