"""Tests for tool base class."""

from harnessgenj_dev.tools.base import BaseTool, ToolResult


class TestToolResult:
    """Test ToolResult dataclass."""

    def test_success_result(self):
        r = ToolResult(success=True, content="OK")
        assert r.success is True
        assert r.content == "OK"
        assert r.error == ""

    def test_error_result(self):
        r = ToolResult(success=False, error="Something failed")
        assert r.success is False
        assert r.error == "Something failed"

    def test_result_with_metadata(self):
        r = ToolResult(success=True, content="data", metadata={"path": "/tmp"})
        assert r.metadata["path"] == "/tmp"

    def test_default_values(self):
        r = ToolResult(success=True)
        assert r.content == ""
        assert r.error == ""
        assert r.metadata is None


class TestBaseTool:
    """Test BaseTool abstract class."""

    def test_base_tool_has_name(self):
        """BaseTool should have name attribute."""
        assert hasattr(BaseTool, "name")

    def test_base_tool_has_schema(self):
        """BaseTool should have schema method."""
        assert hasattr(BaseTool, "schema")

    def test_tool_result_creation(self):
        r = ToolResult(success=True, content="test")
        assert r.success
