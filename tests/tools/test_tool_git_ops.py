"""Tests for git operations tools."""
from harnessgenj_dev.tools.git_ops import GitStatusTool, GitDiffTool, GitLogTool


class TestGitStatusTool:
    """Test git status functionality."""

    def test_git_status(self):
        tool = GitStatusTool()
        result = tool.execute()
        # Git status should always succeed in a git repo
        assert result is not None


class TestGitDiffTool:
    """Test git diff functionality."""

    def test_git_diff(self):
        tool = GitDiffTool()
        result = tool.execute()
        # May have no diff, but should not error
        assert result is not None

    def test_git_diff_cached(self):
        tool = GitDiffTool()
        result = tool.execute(cached=True)
        assert result is not None


class TestGitLogTool:
    """Test git log functionality."""

    def test_git_log(self):
        tool = GitLogTool()
        result = tool.execute()
        # Should return log entries
        assert result is not None

    def test_git_log_with_limit(self):
        tool = GitLogTool()
        result = tool.execute(limit=5)
        assert result is not None
