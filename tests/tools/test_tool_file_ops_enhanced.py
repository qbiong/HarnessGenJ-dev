"""Tests for EditFileTool and enhanced file_ops coverage."""

import os
import asyncio
import tempfile

import pytest

from harnessgenj_dev.tools.file_ops import ReadFileTool, WriteFileTool, EditFileTool, ListDirectoryTool


class TestReadFileToolLineRanges:
    """Test ReadFileTool line range parameters."""

    @pytest.mark.asyncio
    async def test_read_with_line_range(self):
        """Read specific line range."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            for i in range(10):
                f.write(f"line {i}\n")
            path = f.name

        try:
            tool = ReadFileTool()
            result = await tool.execute(path=path, line_start=2, line_end=5)
            assert result.success is True
            assert "line 2" in result.content
            assert "line 4" in result.content
            assert "line 5" not in result.content  # end is exclusive
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_read_with_line_start_only(self):
        """Read from line_start to end of file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            for i in range(5):
                f.write(f"line {i}\n")
            path = f.name

        try:
            tool = ReadFileTool()
            result = await tool.execute(path=path, line_start=3)
            assert result.success is True
            assert "line 3" in result.content
            assert "line 4" in result.content
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_read_out_of_range_lines(self):
        """Reading beyond file length should still work."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("only one line\n")
            path = f.name

        try:
            tool = ReadFileTool()
            result = await tool.execute(path=path, line_start=100, line_end=200)
            assert result.success is True
            # Should return empty or truncated content
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self):
        tool = ReadFileTool()
        result = await tool.execute(path="/nonexistent_file_xyz.py")
        assert result.success is False


class TestWriteFileTool:
    """Test WriteFileTool edge cases."""

    @pytest.mark.asyncio
    async def test_append_mode(self):
        """Write in append mode should not overwrite."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("original\n")
            path = f.name

        try:
            tool = WriteFileTool()
            result = await tool.execute(path=path, content="appended\n", mode="append")
            assert result.success is True
            with open(path) as f:
                content = f.read()
            assert "original" in content
            assert "appended" in content
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_create_nested_directories(self):
        """Should create parent directories when writing to nested path."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "a", "b", "c", "file.txt")
            tool = WriteFileTool()
            result = await tool.execute(path=path, content="nested content")
            assert result.success is True
            assert os.path.exists(path)

    @pytest.mark.asyncio
    async def test_write_empty_content(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("previous content")
            path = f.name

        try:
            tool = WriteFileTool()
            result = await tool.execute(path=path, content="")
            assert result.success is True
            with open(path) as f:
                assert f.read() == ""
        finally:
            os.unlink(path)


class TestEditFileTool:
    """Test EditFileTool — previously completely untested."""

    @pytest.mark.asyncio
    async def test_simple_edit(self):
        """Replace a single occurrence."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def hello():\n    print('hello')\n")
            path = f.name

        try:
            tool = EditFileTool()
            result = await tool.execute(
                path=path,
                old_string="print('hello')",
                new_string="print('world')",
            )
            assert result.success is True
            with open(path) as f:
                content = f.read()
            assert "print('world')" in content
            assert "print('hello')" not in content
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_edit_file_not_found(self):
        tool = EditFileTool()
        result = await tool.execute(
            path="/nonexistent_xyz.py",
            old_string="x",
            new_string="y",
        )
        assert result.success is False
        assert "not found" in result.error.lower() or "error" in result.error.lower()

    @pytest.mark.asyncio
    async def test_old_string_not_found(self):
        """If old_string is not in file, should return error with count 0."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def hello(): pass\n")
            path = f.name

        try:
            tool = EditFileTool()
            result = await tool.execute(
                path=path,
                old_string="nonexistent_text_xyz",
                new_string="replacement",
            )
            assert result.success is False
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_multiple_occurrences_without_replace_all(self):
        """Multiple occurrences without replace_all should return error with count."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("x = 1\nx = 1\n")
            path = f.name

        try:
            tool = EditFileTool()
            result = await tool.execute(
                path=path,
                old_string="x = 1",
                new_string="x = 2",
                replace_all=False,
            )
            assert result.success is False
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_replace_all(self):
        """Replace all occurrences with replace_all=True."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("x = 1\ny = 2\nx = 1\n")
            path = f.name

        try:
            tool = EditFileTool()
            result = await tool.execute(
                path=path,
                old_string="x = 1",
                new_string="x = 99",
                replace_all=True,
            )
            assert result.success is True
            with open(path) as f:
                content = f.read()
            assert content.count("x = 99") == 2
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_edit_preview_in_metadata(self):
        """Edit result should include preview in metadata."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("old = True\n")
            path = f.name

        try:
            tool = EditFileTool()
            result = await tool.execute(
                path=path,
                old_string="old = True",
                new_string="new = True",
            )
            assert result.success is True
            assert result.metadata is not None
        finally:
            os.unlink(path)


class TestListDirectoryTool:
    """Test ListDirectoryTool."""

    @pytest.mark.asyncio
    async def test_list_directory(self):
        tool = ListDirectoryTool()
        result = await tool.execute(path=os.path.dirname(__file__))
        assert result.success is True
        # Output should have D or F prefixes (space-separated)
        assert "D " in result.content or "F " in result.content

    @pytest.mark.asyncio
    async def test_list_file_path(self):
        """Passing a file path should return error."""
        tool = ListDirectoryTool()
        result = await tool.execute(path=__file__)
        assert result.success is False

    @pytest.mark.asyncio
    async def test_list_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            tool = ListDirectoryTool()
            result = await tool.execute(path=tmp)
            assert result.success is True
            # Should indicate empty directory
            assert "empty" in result.content.lower() or result.content.strip() == ""
