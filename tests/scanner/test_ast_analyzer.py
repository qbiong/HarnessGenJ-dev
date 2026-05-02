"""Tests for AST analyzer."""

import os
import tempfile

from harnessgenj_dev.scanner.ast_analyzer import PythonASTAnalyzer, SymbolInfo, FileAnalysis


class TestPythonASTAnalyzer:
    """Test Python AST analysis."""

    def test_create_analyzer(self):
        analyzer = PythonASTAnalyzer()
        assert analyzer is not None

    def test_analyze_simple_code(self):
        analyzer = PythonASTAnalyzer()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def foo():\n    return 42\n")
            tmp = f.name
        try:
            result = analyzer.analyze_file(tmp)
            assert result.language == "python"
            names = [s.name for s in result.symbols]
            assert "foo" in names
        finally:
            os.unlink(tmp)

    def test_analyze_class(self):
        analyzer = PythonASTAnalyzer()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("class MyClass:\n    def method(self): pass\n")
            tmp = f.name
        try:
            result = analyzer.analyze_file(tmp)
            names = [s.name for s in result.symbols]
            assert "MyClass" in names
            assert "method" in names
        finally:
            os.unlink(tmp)

    def test_analyze_empty_code(self):
        analyzer = PythonASTAnalyzer()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("")
            tmp = f.name
        try:
            result = analyzer.analyze_file(tmp)
            assert result is not None
            assert result.symbols == []
        finally:
            os.unlink(tmp)

    def test_analyze_invalid_syntax(self):
        analyzer = PythonASTAnalyzer()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def foo(")
            tmp = f.name
        try:
            result = analyzer.analyze_file(tmp)
            assert result is not None
            assert result.symbols == []
        finally:
            os.unlink(tmp)
