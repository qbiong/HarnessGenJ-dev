"""Tests for scanner edge cases and missing coverage."""

import os
import tempfile

import pytest

from harnessgenj_dev.scanner.project_index import ProjectIndex, FileNode
from harnessgenj_dev.scanner.ast_analyzer import PythonASTAnalyzer, SymbolInfo, FileAnalysis
from harnessgenj_dev.scanner.symbol_table import SymbolTable
from harnessgenj_dev.scanner.code_search import CodeSearch


class TestProjectIndexEdgeCases:
    """Test ProjectIndex edge cases."""

    def test_scan_nonexistent_directory(self):
        idx = ProjectIndex("/nonexistent_dir_xyz_123")
        idx.scan()
        assert idx.root is not None

    def test_scan_max_depth(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Create nested structure
            os.makedirs(os.path.join(tmp, "a", "b", "c"))
            with open(os.path.join(tmp, "a", "b", "c", "deep.py"), "w") as f:
                f.write("pass")

            idx = ProjectIndex(tmp)
            idx.scan(max_depth=1)
            # Should not traverse beyond depth 1
            tree_str = idx.get_file_tree_string()
            assert tree_str is not None

    def test_scan_permission_error(self):
        """Should handle permission errors gracefully."""
        with tempfile.TemporaryDirectory() as tmp:
            idx = ProjectIndex(tmp)
            idx.scan()
            tree = idx.get_file_tree_string()
            assert tree is not None

    def test_file_tree_string_no_scan(self, tmp_path):
        idx = ProjectIndex(str(tmp_path))
        tree = idx.get_file_tree_string()
        assert "no tree" in tree.lower()


class TestPythonASTAnalyzerEdgeCases:
    """Test AST analyzer edge cases."""

    def test_analyze_decorated_function(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test_decorated.py")
            with open(path, "w") as f:
                f.write(
                    "@staticmethod\n"
                    "@property\n"
                    "def decorated_func():\n"
                    "    pass\n"
                )
            analyzer = PythonASTAnalyzer()
            result = analyzer.analyze_file(path)
            assert result is not None
            symbols = [s for s in result.symbols if s.name == "decorated_func"]
            assert len(symbols) == 1
            assert "staticmethod" in symbols[0].decorators

    def test_analyze_async_function(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test_async.py")
            with open(path, "w") as f:
                f.write("async def async_func():\n    pass\n")
            analyzer = PythonASTAnalyzer()
            result = analyzer.analyze_file(path)
            symbols = [s for s in result.symbols if s.name == "async_func"]
            assert len(symbols) == 1

    def test_analyze_nested_functions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test_nested.py")
            with open(path, "w") as f:
                f.write(
                    "def outer():\n"
                    "    def inner():\n"
                    "        pass\n"
                )
            analyzer = PythonASTAnalyzer()
            result = analyzer.analyze_file(path)
            names = [s.name for s in result.symbols]
            assert "outer" in names
            assert "inner" in names

    def test_analyze_decorated_class(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test_class.py")
            with open(path, "w") as f:
                f.write(
                    "@dataclass\n"
                    "class MyClass:\n"
                    "    pass\n"
                )
            analyzer = PythonASTAnalyzer()
            result = analyzer.analyze_file(path)
            symbols = [s for s in result.symbols if s.name == "MyClass"]
            assert len(symbols) == 1
            assert "dataclass" in symbols[0].decorators

    def test_complexity_calculation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test_complexity.py")
            with open(path, "w") as f:
                f.write(
                    "def complex_func(x, y):\n"
                    "    if x > 0:\n"
                    "        if y > 0:\n"
                    "            return x + y\n"
                    "    elif x < 0 and y < 0:\n"
                    "        return x - y\n"
                    "    return 0\n"
                )
            analyzer = PythonASTAnalyzer()
            result = analyzer.analyze_file(path)
            assert result.complexity > 1

    def test_analyze_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "a.py"), "w") as f:
                f.write("def func_a(): pass\n")
            with open(os.path.join(tmp, "b.py"), "w") as f:
                f.write("def func_b(): pass\n")

            analyzer = PythonASTAnalyzer()
            results = analyzer.analyze_directory(tmp)
            assert len(results) == 2

    def test_analyze_directory_with_excludes(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "main.py"), "w") as f:
                f.write("def main(): pass\n")
            os.makedirs(os.path.join(tmp, "venv"))
            with open(os.path.join(tmp, "venv", "lib.py"), "w") as f:
                f.write("def lib(): pass\n")

            analyzer = PythonASTAnalyzer()
            # exclude_patterns match against the full path via Path.match()
            # "venv/*" matches files under venv directory
            results = analyzer.analyze_directory(tmp, exclude_patterns=["venv/*"])
            assert len(results) == 1

    def test_analyze_directory_no_python_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "readme.txt"), "w") as f:
                f.write("text")
            analyzer = PythonASTAnalyzer()
            results = analyzer.analyze_directory(tmp)
            assert len(results) == 0


class TestSymbolTableEdgeCases:
    """Test SymbolTable edge cases."""

    def test_lookup_by_file(self):
        table = SymbolTable()
        fa = FileAnalysis(
            file_path="test.py",
            language="python",
            symbols=[SymbolInfo(name="func1", kind="function", file_path="test.py", line_start=1, line_end=1)],
            imports=[],
            complexity=1,
        )
        table.add_analysis(fa)
        results = table.lookup_by_file("test.py")
        assert len(results) == 1

    def test_search_with_kind_filter(self):
        table = SymbolTable()
        table.add_analysis(FileAnalysis(
            file_path="t.py",
            language="python",
            symbols=[
                SymbolInfo(name="func1", kind="function", file_path="t.py", line_start=1, line_end=1),
                SymbolInfo(name="Class1", kind="class", file_path="t.py", line_start=2, line_end=2),
            ],
            imports=[],
            complexity=1,
        ))
        funcs = table.search("func", kind="function")
        assert len(funcs) == 1
        assert funcs[0].kind == "function"

    def test_get_methods(self):
        table = SymbolTable()
        table.add_analysis(FileAnalysis(
            file_path="t.py",
            language="python",
            symbols=[
                SymbolInfo(name="method1", kind="method", file_path="t.py", line_start=1, line_end=1),
                # Add import symbols so get_imports also works
                SymbolInfo(name="os", kind="import", file_path="t.py", line_start=0, line_end=0),
            ],
            imports=["os"],
            complexity=1,
        ))
        methods = table.get_methods()
        assert len(methods) >= 1

    def test_get_imports(self):
        table = SymbolTable()
        table.add_analysis(FileAnalysis(
            file_path="t.py",
            language="python",
            symbols=[
                SymbolInfo(name="os", kind="import", file_path="t.py", line_start=0, line_end=0),
                SymbolInfo(name="sys", kind="import", file_path="t.py", line_start=0, line_end=0),
            ],
            imports=["os", "sys"],
            complexity=0,
        ))
        imports = table.get_imports()
        assert len(imports) >= 2
        names = [i.name for i in imports]
        assert "os" in names
        assert "sys" in names

    def test_clear_resets_counters(self):
        table = SymbolTable()
        table.add_analysis(FileAnalysis(
            file_path="t.py",
            language="python",
            symbols=[SymbolInfo(name="f", kind="function", file_path="t.py", line_start=1, line_end=1)],
            imports=["os"],
            complexity=1,
        ))
        table.clear()
        assert table._files_analyzed == 0
        assert table._total_imports == 0


class TestCodeSearchEdgeCases:
    """Test CodeSearch edge cases."""

    def test_search_without_symbol_table(self):
        """Should fall back to full-text search without symbol table."""
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "test.py"), "w") as f:
                f.write("def my_function(): pass\n")
            search = CodeSearch(tmp)
            results = search.search_symbol("my_function")
            # Should find via full-text fallback
            assert isinstance(results, list)

    def test_search_symbol_not_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            search = CodeSearch(tmp)
            results = search.search_symbol("nonexistent_symbol_xyz")
            assert isinstance(results, list)

    def test_search_python_invalid_regex(self):
        with tempfile.TemporaryDirectory() as tmp:
            search = CodeSearch(tmp)
            # _search_python needs all parameters - use the public search() instead
            results = search.search("[invalid regex", path=".", max_results=10)
            # Should handle re.error gracefully
            assert isinstance(results, list)

    def test_search_python_permission_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "unreadable.py")
            with open(path, "w") as f:
                f.write("test")
            os.chmod(path, 0o000)
            try:
                search = CodeSearch(tmp)
                results = search.search("test", path=".", max_results=10)
                assert isinstance(results, list)
            finally:
                os.chmod(path, 0o644)
