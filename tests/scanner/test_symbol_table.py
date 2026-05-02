"""Tests for symbol table."""

from harnessgenj_dev.scanner.ast_analyzer import FileAnalysis, SymbolInfo
from harnessgenj_dev.scanner.symbol_table import SymbolTable


class TestSymbolTable:
    """Test symbol table functionality."""

    def test_create_table(self):
        table = SymbolTable()
        assert table is not None

    def test_add_symbol(self):
        """Adding analysis should populate symbols."""
        table = SymbolTable()
        analysis = FileAnalysis(
            file_path="test.py",
            language="python",
            symbols=[SymbolInfo(name="my_function", kind="function", file_path="test.py", line_start=1, line_end=5)],
            imports=[],
        )
        table.add_analysis(analysis)
        assert len(table._symbols) == 1

    def test_add_multiple_symbols(self):
        """Adding multiple analyses should accumulate symbols."""
        table = SymbolTable()
        analysis = FileAnalysis(
            file_path="test.py",
            language="python",
            symbols=[
                SymbolInfo(name="func1", kind="function", file_path="test.py", line_start=1, line_end=5),
                SymbolInfo(name="Class1", kind="class", file_path="test.py", line_start=5, line_end=10),
                SymbolInfo(name="var1", kind="variable", file_path="test.py", line_start=10, line_end=11),
            ],
            imports=[],
        )
        table.add_analysis(analysis)
        assert len(table._symbols) == 3

    def test_get_symbol_by_name(self):
        """Should find symbols by exact name match."""
        table = SymbolTable()
        analysis = FileAnalysis(
            file_path="test.py",
            language="python",
            symbols=[SymbolInfo(name="target", kind="function", file_path="test.py", line_start=1, line_end=5)],
            imports=[],
        )
        table.add_analysis(analysis)
        found = table.lookup_by_name("target")
        assert len(found) == 1

    def test_clear_table(self):
        """Clear should reset all symbols."""
        table = SymbolTable()
        analysis = FileAnalysis(
            file_path="test.py",
            language="python",
            symbols=[SymbolInfo(name="func", kind="function", file_path="test.py", line_start=1, line_end=5)],
            imports=[],
        )
        table.add_analysis(analysis)
        table.clear()
        summary = table.summary()
        assert summary["total_symbols"] == 0

    def test_lookup_by_kind(self):
        """Should find symbols by kind."""
        table = SymbolTable()
        analysis = FileAnalysis(
            file_path="test.py",
            language="python",
            symbols=[
                SymbolInfo(name="func1", kind="function", file_path="test.py", line_start=1, line_end=5),
                SymbolInfo(name="Class1", kind="class", file_path="test.py", line_start=5, line_end=10),
            ],
            imports=[],
        )
        table.add_analysis(analysis)
        funcs = table.lookup_by_kind("function")
        assert len(funcs) == 1
        assert funcs[0].name == "func1"

    def test_summary(self):
        """Summary should return correct counts."""
        table = SymbolTable()
        analysis = FileAnalysis(
            file_path="test.py",
            language="python",
            symbols=[SymbolInfo(name="f", kind="function", file_path="test.py", line_start=1, line_end=5)],
            imports=["os", "sys"],
        )
        table.add_analysis(analysis)
        summary = table.summary()
        assert summary["files_analyzed"] == 1
        assert summary["total_symbols"] == 1
        assert summary["total_imports"] == 2
