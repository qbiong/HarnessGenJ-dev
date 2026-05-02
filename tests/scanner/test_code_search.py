"""Tests for code search."""

import os
import tempfile

from harnessgenj_dev.scanner.code_search import CodeSearch, SearchResult


class TestCodeSearch:
    """Test code search functionality."""

    def test_create_search(self):
        search = CodeSearch(".")
        assert search is not None

    def test_search_in_directory(self):
        """Search should return results for common pattern."""
        search = CodeSearch(".")
        results = search.search("def")
        assert isinstance(results, list)

    def test_search_with_no_results(self):
        """Search for unique string should return no results."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create a file with known content
            with open(os.path.join(tmp_dir, "test.py"), "w") as f:
                f.write("def hello(): pass\n")
            search = CodeSearch(tmp_dir)
            search._has_rg = False  # Force Python fallback
            results = search.search("XYZNONEXISTENT123456")
            assert len(results) == 0

    def test_search_by_file_type(self):
        """Search should filter by file type."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            with open(os.path.join(tmp_dir, "test.py"), "w") as f:
                f.write("def hello(): pass\n")
            with open(os.path.join(tmp_dir, "data.txt"), "w") as f:
                f.write("def not_a_function\n")
            search = CodeSearch(tmp_dir)
            search._has_rg = False
            results = search.search("def", file_type=".py")
            assert len(results) >= 1
            assert all(r.file_path.endswith(".py") for r in results)


class TestSearchResult:
    """Test SearchResult dataclass."""

    def test_highlighted(self):
        result = SearchResult(
            file_path="test.py",
            line_number=1,
            line_content="def hello_world(): pass",
            match_start=4,
            match_end=15,
        )
        highlighted = result.highlighted()
        assert "hello_world" in highlighted
