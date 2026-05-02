"""Tests for tools module."""

import pytest


@pytest.mark.asyncio
async def test_read_file_tool(temp_dir):
    """Test file read tool."""
    test_file = temp_dir / "test.txt"
    test_file.write_text("Hello, World!", encoding="utf-8")

    from harnessgenj_dev.tools.file_ops import ReadFileTool

    tool = ReadFileTool()
    result = await tool.execute(path=str(test_file))
    assert result.success
    assert "Hello, World!" in result.content


@pytest.mark.asyncio
async def test_write_file_tool(temp_dir):
    """Test file write tool."""
    test_file = temp_dir / "output.txt"

    from harnessgenj_dev.tools.file_ops import WriteFileTool

    tool = WriteFileTool()
    result = await tool.execute(path=str(test_file), content="Test content")
    assert result.success
    assert test_file.read_text(encoding="utf-8") == "Test content"


@pytest.mark.asyncio
async def test_read_file_not_found():
    """Test reading non-existent file."""
    from harnessgenj_dev.tools.file_ops import ReadFileTool

    tool = ReadFileTool()
    result = await tool.execute(path="/nonexistent/file.txt")
    assert not result.success
