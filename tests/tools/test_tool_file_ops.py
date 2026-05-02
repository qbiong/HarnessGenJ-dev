"""Tests for file operations tools."""

import tempfile
import os
import asyncio

from harnessgenj_dev.tools.file_ops import ReadFileTool, WriteFileTool, ListDirectoryTool


class TestReadFileTool:
    """Test file reading functionality."""

    def test_read_file(self):
        tool = ReadFileTool()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("test content")
            tmp = f.name
        try:
            result = asyncio.get_event_loop().run_until_complete(tool.execute(path=tmp))
            assert result.success
            assert "test content" in result.content
        finally:
            os.unlink(tmp)

    def test_read_nonexistent_file(self):
        tool = ReadFileTool()
        result = asyncio.get_event_loop().run_until_complete(tool.execute(path="/nonexistent/path/file.txt"))
        assert not result.success


class TestWriteFileTool:
    """Test file writing functionality."""

    def test_write_file(self):
        tool = WriteFileTool()
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = os.path.join(tmp_dir, "test.txt")
            result = asyncio.get_event_loop().run_until_complete(tool.execute(path=tmp, content="test content"))
            assert result.success
            assert os.path.exists(tmp)
            with open(tmp, "r") as f:
                assert f.read() == "test content"


class TestListDirectoryTool:
    """Test directory listing functionality."""

    def test_list_directory(self):
        tool = ListDirectoryTool()
        result = asyncio.get_event_loop().run_until_complete(tool.execute(path="."))
        assert result.success

    def test_list_nonexistent_directory(self):
        tool = ListDirectoryTool()
        result = asyncio.get_event_loop().run_until_complete(tool.execute(path="/nonexistent/dir/path"))
        assert not result.success
