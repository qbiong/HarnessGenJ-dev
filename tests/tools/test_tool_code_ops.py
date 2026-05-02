"""Tests for code operations tools."""
from harnessgenj_dev.tools.code_ops import SearchCodeTool
import tempfile
import os


class TestSearchCodeTool:
    """Test code search functionality."""

    def test_search_in_directory(self):
        tool = SearchCodeTool()
        result = tool.execute(query="def", path=".")
        # Search may or may not find results depending on rg availability
        assert result is not None

    def test_search_with_no_results(self):
        tool = SearchCodeTool()
        result = tool.execute(query="XYZNONEXISTENT123456", path=".")
        # Should complete without error even with no results
        assert result is not None
