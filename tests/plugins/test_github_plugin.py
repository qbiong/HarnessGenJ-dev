"""Tests for built-in GitHub plugin."""

import json
import os
import tempfile

import pytest

from harnessgenj_dev.plugins.builtins import GitHubPlugin, register_builtin_plugins
from harnessgenj_dev.plugins.registry import PluginRegistry


class TestGitHubPluginInfo:
    """Test plugin metadata."""

    def test_plugin_info(self):
        p = GitHubPlugin()
        assert p.info.name == "github"
        assert p.info.version == "0.1.0"
        assert "GitHub integration" in p.info.description

    def test_plugin_is_abstract(self):
        """Plugin class should be instantiable."""
        p = GitHubPlugin()
        assert p is not None


class TestGitHubPluginLifecycle:
    """Test plugin lifecycle methods."""

    @pytest.mark.asyncio
    async def test_initialize_without_config(self):
        p = GitHubPlugin()
        await p.initialize()
        assert p._token == ""
        await p.shutdown()

    @pytest.mark.asyncio
    async def test_initialize_with_config(self):
        p = GitHubPlugin()
        await p.initialize(
            config={"owner": "test-org", "repo": "test-repo", "token": "gh_test"}
        )
        assert p._owner == "test-org"
        assert p._repo == "test-repo"
        assert p._token == "gh_test"
        await p.shutdown()

    @pytest.mark.asyncio
    async def test_initialize_with_env_token(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "gh_env_token")
        p = GitHubPlugin()
        await p.initialize(config={"owner": "o", "repo": "r"})
        assert p._token == "gh_env_token"
        await p.shutdown()

    @pytest.mark.asyncio
    async def test_initialize_with_custom_base_url(self):
        p = GitHubPlugin()
        await p.initialize(
            config={
                "owner": "o",
                "repo": "r",
                "token": "t",
                "base_url": "https://gh.example.com/api/v3",
            }
        )
        assert p._base_url == "https://gh.example.com/api/v3"
        await p.shutdown()

    @pytest.mark.asyncio
    async def test_shutdown_closes_client(self):
        p = GitHubPlugin()
        await p.initialize(config={"owner": "o", "repo": "r", "token": "t"})
        assert p._client is not None
        await p.shutdown()
        assert p._client is None


class TestGitHubPluginHooks:
    """Test hook registrations."""

    def test_get_hooks(self):
        p = GitHubPlugin()
        hooks = p.get_hooks()
        assert "pre_develop" in hooks
        assert "post_develop" in hooks
        assert "pre_review" in hooks

    @pytest.mark.asyncio
    async def test_pre_develop_hook(self):
        p = GitHubPlugin()
        await p.initialize(config={"owner": "o", "repo": "r", "token": "t"})
        result = await p.get_hooks()["pre_develop"]()
        assert result["plugin"] == "github"
        assert result["hook"] == "pre_develop"
        assert result["repo"] == "o/r"
        await p.shutdown()

    @pytest.mark.asyncio
    async def test_post_develop_hook(self):
        p = GitHubPlugin()
        await p.initialize(config={"owner": "o", "repo": "r", "token": "t"})
        result = await p.get_hooks()["post_develop"]()
        assert result["plugin"] == "github"
        assert result["hook"] == "post_develop"
        await p.shutdown()

    @pytest.mark.asyncio
    async def test_pre_review_hook_no_repo(self):
        p = GitHubPlugin()
        await p.initialize()  # No repo configured
        result = await p.get_hooks()["pre_review"]()
        assert result["plugin"] == "github"
        assert result["issue_count"] == 0
        await p.shutdown()


class TestGitHubPluginCommands:
    """Test CLI commands."""

    def test_get_commands(self):
        p = GitHubPlugin()
        cmds = p.get_commands()
        assert "github_issues" in cmds
        assert "github_pr_info" in cmds
        assert "github_create_issue" in cmds

    @pytest.mark.asyncio
    async def test_commands_are_coroutines(self):
        p = GitHubPlugin()
        cmds = p.get_commands()
        import inspect
        for name, fn in cmds.items():
            assert inspect.iscoroutinefunction(fn), f"{name} should be async"


class TestGitHubPluginApiErrors:
    """Test error handling for API methods."""

    @pytest.mark.asyncio
    async def test_request_without_init(self):
        p = GitHubPlugin()
        with pytest.raises(RuntimeError, match="not initialized"):
            await p._request("GET", "/repos/o/r/issues")

    @pytest.mark.asyncio
    async def test_list_issues_missing_owner(self):
        p = GitHubPlugin()
        await p.initialize(config={"token": "t"})
        with pytest.raises(ValueError, match="owner and repo are required"):
            await p.list_issues()
        await p.shutdown()

    @pytest.mark.asyncio
    async def test_create_issue_missing_owner(self):
        p = GitHubPlugin()
        await p.initialize(config={"token": "t"})
        with pytest.raises(ValueError, match="owner and repo are required"):
            await p.create_issue("Test issue")
        await p.shutdown()

    @pytest.mark.asyncio
    async def test_get_pr_missing_owner(self):
        p = GitHubPlugin()
        await p.initialize(config={"token": "t"})
        with pytest.raises(ValueError, match="owner and repo are required"):
            await p.get_pull_request(1)
        await p.shutdown()

    @pytest.mark.asyncio
    async def test_comment_pr_missing_owner(self):
        p = GitHubPlugin()
        await p.initialize(config={"token": "t"})
        with pytest.raises(ValueError, match="owner and repo are required"):
            await p.comment_on_pr(1, "comment")
        await p.shutdown()


class TestGitHubPluginGetTools:
    """Test tool registration."""

    def test_get_tools_empty_by_default(self):
        p = GitHubPlugin()
        # This plugin doesn't provide tool classes (only commands and hooks)
        tools = p.get_tools()
        assert tools == []


class TestRegisterBuiltins:
    """Test the register_builtin_packages function."""

    def test_register_builtin_plugins(self):
        registry = PluginRegistry()
        register_builtin_plugins(registry)
        assert registry.plugin_count >= 1
        assert "github" in registry.plugin_names
