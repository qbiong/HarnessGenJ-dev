"""Tests for scanner module: AST analyzer, symbol table, and code search."""

import os
import tempfile
from pathlib import Path

import pytest


# --- AST Analyzer Tests ---

def test_analyze_single_file():
    """Test analyzing a single Python file."""
    from harnessgenj_dev.scanner.ast_analyzer import PythonASTAnalyzer

    # Create a temp Python file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False
    ) as f:
        f.write("""
import os
from pathlib import Path

class MyClass:
    \"\"\"A sample class.\"\"\"

    def __init__(self, name):
        self.name = name

    def greet(self):
        return f"Hello, {self.name}"

def standalone_function(x, y):
    \"\"\"A standalone function.\"\"\"
    return x + y
""")
        tmp_path = f.name

    try:
        analyzer = PythonASTAnalyzer()
        result = analyzer.analyze_file(tmp_path)

        assert result.language == "python"
        assert len(result.symbols) > 0

        # Should have found MyClass, __init__, greet, standalone_function
        names = [s.name for s in result.symbols]
        assert "MyClass" in names
        assert "__init__" in names
        assert "greet" in names
        assert "standalone_function" in names

        # Should have found imports
        assert "os" in result.imports
        assert "pathlib.Path" in result.imports
    finally:
        os.unlink(tmp_path)


def test_analyze_syntax_error():
    """Test analyzing a file with syntax errors returns gracefully."""
    from harnessgenj_dev.scanner.ast_analyzer import PythonASTAnalyzer

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False
    ) as f:
        f.write("def broken(\n  # syntax error")
        tmp_path = f.name

    try:
        analyzer = PythonASTAnalyzer()
        result = analyzer.analyze_file(tmp_path)

        assert result.symbols == []
        assert result.imports == []
    finally:
        os.unlink(tmp_path)


def test_analyze_directory():
    """Test analyzing a directory of Python files."""
    from harnessgenj_dev.scanner.ast_analyzer import PythonASTAnalyzer

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create Python files
        with open(os.path.join(tmp_dir, "main.py"), "w") as f:
            f.write("def main(): pass\n")
        with open(os.path.join(tmp_dir, "utils.py"), "w") as f:
            f.write("def helper(): pass\n")

        # Create a non-Python file (should be ignored)
        with open(os.path.join(tmp_dir, "data.txt"), "w") as f:
            f.write("not python")

        # Create a hidden directory (should be skipped)
        hidden_dir = os.path.join(tmp_dir, ".hidden")
        os.makedirs(hidden_dir)
        with open(os.path.join(hidden_dir, "secret.py"), "w") as f:
            f.write("def secret(): pass")

        analyzer = PythonASTAnalyzer()
        results = analyzer.analyze_directory(tmp_dir)

        assert len(results) == 2  # main.py and utils.py only
        all_symbols = []
        for r in results:
            all_symbols.extend(r.symbols)
        names = [s.name for s in all_symbols]
        assert "main" in names
        assert "helper" in names


# --- Symbol Table Tests ---

def test_symbol_table_build():
    """Test building a symbol table from analysis results."""
    from harnessgenj_dev.scanner.ast_analyzer import FileAnalysis, SymbolInfo
    from harnessgenj_dev.scanner.symbol_table import SymbolTable

    table = SymbolTable()

    # Add mock analysis
    analysis = FileAnalysis(
        file_path="test.py",
        language="python",
        symbols=[
            SymbolInfo(name="MyClass", kind="class", file_path="test.py", line_start=1, line_end=10),
            SymbolInfo(name="func", kind="function", file_path="test.py", line_start=12, line_end=15),
        ],
        imports=["os", "sys"],
    )
    table.add_analysis(analysis)

    assert table._files_analyzed == 1
    assert table._total_imports == 2
    assert len(table._symbols) == 2


def test_symbol_table_lookup():
    """Test various lookup methods on symbol table."""
    from harnessgenj_dev.scanner.ast_analyzer import FileAnalysis, SymbolInfo
    from harnessgenj_dev.scanner.symbol_table import SymbolTable

    table = SymbolTable()
    table.add_analysis(FileAnalysis(
        file_path="test.py",
        language="python",
        symbols=[
            SymbolInfo(name="User", kind="class", file_path="src/models.py", line_start=1, line_end=20),
            SymbolInfo(name="get_user", kind="function", file_path="src/api.py", line_start=5, line_end=10),
            SymbolInfo(name="delete_user", kind="function", file_path="src/api.py", line_start=12, line_end=18),
            SymbolInfo(name="User", kind="class", file_path="tests/test_models.py", line_start=1, line_end=5),
        ],
        imports=["os"],
    ))

    # Lookup by name
    users = table.lookup_by_name("User")
    assert len(users) == 2

    # Lookup by kind
    funcs = table.lookup_by_kind("function")
    assert len(funcs) == 2

    # Lookup by file
    api_symbols = table.lookup_by_file("api.py")
    assert len(api_symbols) == 2

    # Fuzzy search (substring match: User, get_user, delete_user, User = 4)
    user_search = table.search("user")
    assert len(user_search) == 4

    # Search with kind filter
    user_funcs = table.search("user", kind="function")
    assert len(user_funcs) == 2  # get_user, delete_user

    # Get helpers
    assert len(table.get_classes()) == 2
    assert len(table.get_functions()) == 2
    assert len(table.get_methods()) == 0


def test_symbol_table_summary():
    """Test symbol table summary statistics."""
    from harnessgenj_dev.scanner.ast_analyzer import FileAnalysis, SymbolInfo
    from harnessgenj_dev.scanner.symbol_table import SymbolTable

    table = SymbolTable()
    table.add_analysis(FileAnalysis(
        file_path="a.py",
        language="python",
        symbols=[
            SymbolInfo(name="A", kind="class", file_path="a.py", line_start=1, line_end=5),
            SymbolInfo(name="b", kind="function", file_path="a.py", line_start=7, line_end=10),
        ],
        imports=["os"],
    ))
    table.add_analysis(FileAnalysis(
        file_path="b.py",
        language="python",
        symbols=[
            SymbolInfo(name="c", kind="method", file_path="b.py", line_start=1, line_end=5),
        ],
        imports=["sys", "json"],
    ))

    summary = table.summary()
    assert summary["files_analyzed"] == 2
    assert summary["total_symbols"] == 3
    assert summary["total_imports"] == 3
    assert summary["by_kind"]["class"] == 1
    assert summary["by_kind"]["function"] == 1
    assert summary["by_kind"]["method"] == 1

    # Test clear
    table.clear()
    assert table.summary()["total_symbols"] == 0


def test_symbol_table_build_from_directory():
    """Test building symbol table directly from a directory."""
    from harnessgenj_dev.scanner.symbol_table import SymbolTable

    with tempfile.TemporaryDirectory() as tmp_dir:
        with open(os.path.join(tmp_dir, "app.py"), "w") as f:
            f.write("""
import os

class App:
    def run(self):
        pass

def main():
    pass
""")
        table = SymbolTable()
        table.build_from_directory(tmp_dir)

        summary = table.summary()
        assert summary["total_symbols"] >= 2  # App + main
        assert summary["files_analyzed"] >= 1


# --- Code Search Tests ---

def test_code_search_python_fallback():
    """Test code search using Python regex fallback."""
    from harnessgenj_dev.scanner.code_search import CodeSearch

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create test files
        with open(os.path.join(tmp_dir, "main.py"), "w") as f:
            f.write("""
def hello(name):
    print(f"Hello, {name}!")

def goodbye(name):
    print(f"Goodbye, {name}!")
""")
        with open(os.path.join(tmp_dir, "test.py"), "w") as f:
            f.write("def test_hello(): pass")

        search = CodeSearch(tmp_dir)
        # Force Python fallback by marking rg as unavailable
        search._has_rg = False

        results = search.search("def hello")
        assert len(results) >= 1
        assert results[0].line_number == 2  # def hello is on line 2
        assert "def hello" in results[0].line_content

        # Test case insensitive
        results_ci = search.search("DEF HELLO", case_sensitive=False)
        assert len(results_ci) >= 1

        # Test max_results
        results_limited = search.search("def", max_results=1)
        assert len(results_limited) == 1

        # Test file_type filter
        results_py = search.search("def", file_type=".py")
        assert len(results_py) >= 1


def test_code_search_word_boundary():
    """Test word boundary search."""
    from harnessgenj_dev.scanner.code_search import CodeSearch

    with tempfile.TemporaryDirectory() as tmp_dir:
        with open(os.path.join(tmp_dir, "app.py"), "w") as f:
            f.write("user_id = 1\nusername = 'admin'\n")

        search = CodeSearch(tmp_dir)
        search._has_rg = False

        # Word search should only match 'user_id' not 'username'
        results = search.search("user_id", word=True)
        assert len(results) == 1
        assert "user_id" in results[0].line_content


def test_code_search_highlight():
    """Test search result highlighting."""
    from harnessgenj_dev.scanner.code_search import SearchResult

    result = SearchResult(
        file_path="test.py",
        line_number=1,
        line_content="def hello_world(): pass",
        match_start=4,
        match_end=15,
    )

    highlighted = result.highlighted()
    assert "hello_world" in highlighted


def test_code_search_symbol():
    """Test symbol search via SymbolTable integration."""
    from harnessgenj_dev.scanner.ast_analyzer import FileAnalysis, SymbolInfo
    from harnessgenj_dev.scanner.code_search import CodeSearch
    from harnessgenj_dev.scanner.symbol_table import SymbolTable

    with tempfile.TemporaryDirectory() as tmp_dir:
        with open(os.path.join(tmp_dir, "app.py"), "w") as f:
            f.write("class App:\n    def run(self): pass\n")

        # Build symbol table
        table = SymbolTable()
        table.build_from_directory(tmp_dir)

        # Search via symbol table
        search = CodeSearch(tmp_dir)
        results = search.search_symbol("App", symbol_table=table)
        assert len(results) >= 1
        assert results[0].line_number == 1
