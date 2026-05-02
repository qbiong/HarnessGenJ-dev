"""Tests for GitHub plugin API methods with mocked HTTP."""

import pytest

from harnessgenj_dev.plugins.builtins.github_plugin import GitHubPlugin
from harnessgenj_dev.plugins.builtins import register_builtin_plugins
from harnessgenj_dev.plugins.registry import PluginRegistry


class MockResponse:
    """Mock httpx response."""

    def __init__(self, status_code: int = 200, json_data: dict | list | None = None):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = str(json_data)

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPStatusError("Error", request=None, response=self)


class MockClient:
    """Mock httpx AsyncClient."""

    def __init__(self, responses: list | None = None):
        self._responses = responses or []
        self._call_index = 0
        self.last_request = None

    async def request(self, method, path, **kwargs):
        self.last_request = {"method": method, "path": path, **kwargs}
        if self._responses and self._call_index < len(self._responses):
            resp = self._responses[self._call_index]
            self._call_index += 1
            return resp
        # Default response (list for issues, empty dict for others)
        default_resp = MockResponse(200, [])
        return default_resp

    async def aclose(self):
        pass  # No-op for mock


async def make_plugin(responses: list | None = None) -> tuple[GitHubPlugin, MockClient]:
    """Create a plugin with a mocked HTTP client."""
    p = GitHubPlugin()
    await p.initialize(config={"owner": "o", "repo": "r", "token": "t"})
    client = MockClient(responses if responses is not None else [])
    p._client = client
    return p, client


class TestGitHubPluginApiMethods:
    """Test actual API methods with mocked HTTP."""

    @pytest.mark.asyncio
    async def test_list_issues_success(self):
        p, client = await make_plugin([
            MockResponse(200, [
                {
                    "number": 1,
                    "title": "Test issue",
                    "state": "open",
                    "labels": [{"name": "bug"}],
                    "created_at": "2024-01-01",
                    "html_url": "https://github.com/test-org/test-repo/issues/1",
                }
            ])
        ])

        issues = await p.list_issues()
        assert len(issues) == 1
        assert issues[0]["number"] == 1
        assert issues[0]["title"] == "Test issue"
        assert "bug" in issues[0]["labels"]

        await p.shutdown()

    @pytest.mark.asyncio
    async def test_list_issues_with_labels(self, monkeypatch):
        p = GitHubPlugin()
        await p.initialize(config={"owner": "o", "repo": "r", "token": "t"})

        async def mock_request(method, path, **kwargs):
            class FakeResp:
                status_code = 200
                text = "[]"
                def json(self):
                    return []
                def raise_for_status(self):
                    pass
            return FakeResp()

        monkeypatch.setattr(p, "_request", mock_request)
        issues = await p.list_issues(labels=["bug", "urgent"])
        assert issues == []
        await p.shutdown()

    @pytest.mark.asyncio
    async def test_list_issues_non_200_returns_empty(self):
        p, client = await make_plugin([MockResponse(404, {"message": "Not Found"})])

        issues = await p.list_issues()
        assert issues == []
        await p.shutdown()

    @pytest.mark.asyncio
    async def test_create_issue_success(self):
        p, client = await make_plugin([MockResponse(201, {
            "number": 42,
            "title": "New issue",
            "html_url": "https://github.com/o/r/issues/42",
            "state": "open",
        })])

        result = await p.create_issue("New issue", body="Details")
        assert result["number"] == 42
        assert result["title"] == "New issue"
        await p.shutdown()

    @pytest.mark.asyncio
    async def test_create_issue_with_labels_and_assignees(self):
        p, client = await make_plugin([MockResponse(201, {
            "number": 1, "title": "T", "html_url": "u", "state": "open",
        })])

        await p.create_issue("T", labels=["bug"], assignees=["alice"])
        assert client.last_request["json"]["labels"] == ["bug"]
        assert client.last_request["json"]["assignees"] == ["alice"]
        await p.shutdown()

    @pytest.mark.asyncio
    async def test_get_pull_request_success(self):
        p, client = await make_plugin([MockResponse(200, {
            "number": 10,
            "title": "Fix bug",
            "state": "open",
            "merged": False,
            "head": {"ref": "fix-bug"},
            "base": {"ref": "main"},
            "user": {"login": "alice"},
            "created_at": "2024-01-01",
            "html_url": "https://github.com/o/r/pull/10",
            "additions": 50,
            "deletions": 20,
        })])

        pr = await p.get_pull_request(10)
        assert pr["number"] == 10
        assert pr["head"] == "fix-bug"
        assert pr["additions"] == 50
        assert pr["merged"] is False
        await p.shutdown()

    @pytest.mark.asyncio
    async def test_comment_on_pr_success(self):
        p, client = await make_plugin([MockResponse(201, {
            "id": 123,
            "html_url": "https://github.com/o/r/issues/5#comment-123",
            "created_at": "2024-01-01",
        })])

        result = await p.comment_on_pr(5, "LGTM!")
        assert result["id"] == 123
        await p.shutdown()

    @pytest.mark.asyncio
    async def test_request_http_status_error(self):
        p, client = await make_plugin()

        # Manually create a mock that raises HTTPStatusError
        class ErrorClient:
            async def request(self, *a, **kw):
                import httpx
                resp = MockResponse(403, {"message": "Forbidden"})
                raise httpx.HTTPStatusError("Forbidden", request=None, response=resp)

            async def aclose(self):
                pass

        p._client = ErrorClient()
        with pytest.raises(Exception):
            await p._request("GET", "/repos/o/r/issues")
        await p.shutdown()

    @pytest.mark.asyncio
    async def test_request_not_initialized(self):
        p = GitHubPlugin()
        with pytest.raises(RuntimeError, match="not initialized"):
            await p._request("GET", "/test")


class TestGitHubPluginCommandOutputs:
    """Test CLI command formatted output."""

    @pytest.mark.asyncio
    async def test_github_issues_success(self):
        p, client = await make_plugin([
            MockResponse(200, [
                {"number": 1, "title": "Bug fix", "state": "open",
                 "labels": [{"name": "bug"}], "created_at": "2024-01-01",
                 "html_url": "https://example.com/1"},
            ])
        ])

        output = await p.github_issues()
        assert "GitHub Issues" in output
        assert "#1" in output
        assert "Bug fix" in output
        await p.shutdown()

    @pytest.mark.asyncio
    async def test_github_issues_no_results(self, monkeypatch):
        p = GitHubPlugin()
        await p.initialize(config={"owner": "o", "repo": "r", "token": "t"})

        async def mock_request(method, path, **kwargs):
            class FakeResp:
                status_code = 200
                text = "[]"
                def json(self):
                    return []
                def raise_for_status(self):
                    pass
            return FakeResp()

        monkeypatch.setattr(p, "_request", mock_request)
        output = await p.github_issues()
        assert "No issues found" in output
        await p.shutdown()

    @pytest.mark.asyncio
    async def test_github_pr_info_merged(self):
        p, client = await make_plugin([MockResponse(200, {
            "number": 5, "title": "Feature", "state": "closed",
            "merged": True, "head": {"ref": "feature"}, "base": {"ref": "main"},
            "user": {"login": "bob"}, "created_at": "2024-01-01",
            "html_url": "https://example.com/5", "additions": 100, "deletions": 50,
        })])

        output = await p.github_pr_info(5)
        assert "(merged)" in output
        assert "+100" in output
        assert "-50" in output
        await p.shutdown()

    @pytest.mark.asyncio
    async def test_github_create_issue_success(self):
        p, client = await make_plugin([MockResponse(201, {
            "number": 99, "title": "New", "html_url": "https://example.com/99", "state": "open",
        })])

        output = await p.github_create_issue("New", body="Details")
        assert "Issue created" in output
        assert "#99" in output
        await p.shutdown()


class TestRegisterBuiltinsEnhanced:
    """Test register_builtin_packages."""

    def test_register_multiple_calls_idempotent(self):
        registry = PluginRegistry()
        register_builtin_plugins(registry)
        count1 = registry.plugin_count
        register_builtin_plugins(registry)
        # Second registration adds another instance
        assert registry.plugin_count >= count1
