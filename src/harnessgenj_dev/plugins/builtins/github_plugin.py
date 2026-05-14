"""GitHub Integration Plugin for HarnessGenJ-dev.

Provides GitHub API integration for listing issues, creating issues,
getting pull request info, and commenting on PRs. Also registers hooks
for pre_develop, post_develop, and pre_review lifecycle events.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from ..base import Plugin, PluginInfo

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"


class GitHubPlugin(Plugin):
    """GitHub integration plugin.

    Provides tools and hooks for interacting with GitHub repositories,
    including issue management and pull request operations.

    Configuration (passed to initialize):
        owner: GitHub repository owner (required)
        repo: GitHub repository name (required)
        token: GitHub personal access token (falls back to GITHUB_TOKEN env var)
        base_url: Custom GitHub API base URL (for Enterprise, optional)
    """

    info = PluginInfo(
        name="github",
        version="0.1.0",
        description="GitHub integration: issues, PRs, and lifecycle hooks",
        author="HarnessGenJ-dev",
    )

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._owner: str = ""
        self._repo: str = ""
        self._token: str = ""
        self._base_url: str = GITHUB_API_BASE

    # --- Plugin lifecycle ---

    async def initialize(self, config: dict[str, Any] | None = None) -> None:
        """Initialize the GitHub plugin.

        Args:
            config: Plugin config with keys: owner, repo, token, base_url.
        """
        config = config or {}
        self._owner = config.get("owner", "")
        self._repo = config.get("repo", "")
        self._token = config.get("token", os.environ.get("GITHUB_TOKEN", ""))
        self._base_url = config.get("base_url", GITHUB_API_BASE)

        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self._token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30.0,
        )

        if not self._token:
            logger.warning(
                "GitHub plugin initialized without a token. Set GITHUB_TOKEN env var or pass 'token' in config."
            )

        if self._owner and self._repo:
            logger.info("GitHub plugin initialized for %s/%s", self._owner, self._repo)
        else:
            logger.info("GitHub plugin initialized (no repo configured)")

    async def shutdown(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("GitHub plugin shutdown")

    # --- CLI commands ---

    def get_commands(self) -> dict[str, Any]:
        """Return CLI commands: github_issues, github_pr_info, github_create_issue."""
        return {
            "github_issues": self.github_issues,
            "github_pr_info": self.github_pr_info,
            "github_create_issue": self.github_create_issue,
        }

    # --- Hook registrations ---

    def get_hooks(self) -> dict[str, Any]:
        """Register hooks for pre_develop, post_develop, pre_review events."""
        return {
            "pre_develop": self._on_pre_develop,
            "post_develop": self._on_post_develop,
            "pre_review": self._on_pre_review,
        }

    # --- Core API methods ---

    async def list_issues(
        self,
        owner: str | None = None,
        repo: str | None = None,
        state: str = "open",
        labels: list[str] | None = None,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        """List issues from a GitHub repository.

        Args:
            owner: Repo owner (uses config default if omitted).
            repo: Repo name (uses config default if omitted).
            state: Issue state — "open", "closed", or "all".
            labels: Optional list of label names to filter by.
            limit: Maximum number of issues to return.

        Returns:
            List of issue dicts with number, title, state, labels, etc.
        """
        owner = owner or self._owner
        repo = repo or self._repo
        if not owner or not repo:
            raise ValueError("owner and repo are required (set in config or pass explicitly)")

        params: dict[str, Any] = {"state": state, "per_page": min(limit, 100)}
        if labels:
            params["labels"] = ",".join(labels)

        try:
            resp = await self._request("GET", f"/repos/{owner}/{repo}/issues", params=params)
            issues = resp.json() if resp.status_code == 200 else []
        except (httpx.HTTPStatusError, httpx.RequestError):
            return []

        return [
            {
                "number": issue["number"],
                "title": issue["title"],
                "state": issue["state"],
                "labels": [lb["name"] for lb in issue.get("labels", [])],
                "created_at": issue.get("created_at", ""),
                "url": issue.get("html_url", ""),
            }
            for issue in issues[:limit]
        ]

    async def create_issue(
        self,
        title: str,
        body: str = "",
        owner: str | None = None,
        repo: str | None = None,
        labels: list[str] | None = None,
        assignees: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a new issue on a GitHub repository.

        Args:
            title: Issue title (required).
            body: Issue body / description.
            owner: Repo owner (uses config default if omitted).
            repo: Repo name (uses config default if omitted).
            labels: Optional labels to apply.
            assignees: Optional usernames to assign.

        Returns:
            Dict with the created issue info.
        """
        owner = owner or self._owner
        repo = repo or self._repo
        if not owner or not repo:
            raise ValueError("owner and repo are required (set in config or pass explicitly)")

        payload: dict[str, Any] = {"title": title, "body": body}
        if labels:
            payload["labels"] = labels
        if assignees:
            payload["assignees"] = assignees

        resp = await self._request("POST", f"/repos/{owner}/{repo}/issues", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return {
            "number": data["number"],
            "title": data["title"],
            "url": data.get("html_url", ""),
            "state": data["state"],
        }

    async def get_pull_request(
        self,
        pr_number: int,
        owner: str | None = None,
        repo: str | None = None,
    ) -> dict[str, Any]:
        """Get information about a specific pull request.

        Args:
            pr_number: Pull request number.
            owner: Repo owner (uses config default if omitted).
            repo: Repo name (uses config default if omitted).

        Returns:
            Dict with PR info (number, title, state, merged, etc.).
        """
        owner = owner or self._owner
        repo = repo or self._repo
        if not owner or not repo:
            raise ValueError("owner and repo are required (set in config or pass explicitly)")

        resp = await self._request("GET", f"/repos/{owner}/{repo}/pulls/{pr_number}")
        resp.raise_for_status()
        data = resp.json()
        return {
            "number": data["number"],
            "title": data["title"],
            "state": data["state"],
            "merged": data.get("merged", False),
            "head": data.get("head", {}).get("ref", ""),
            "base": data.get("base", {}).get("ref", ""),
            "user": data.get("user", {}).get("login", ""),
            "created_at": data.get("created_at", ""),
            "url": data.get("html_url", ""),
            "additions": data.get("additions", 0),
            "deletions": data.get("deletions", 0),
        }

    async def comment_on_pr(
        self,
        pr_number: int,
        body: str,
        owner: str | None = None,
        repo: str | None = None,
    ) -> dict[str, Any]:
        """Add a comment to a pull request.

        Args:
            pr_number: Pull request number.
            body: Comment text.
            owner: Repo owner (uses config default if omitted).
            repo: Repo name (uses config default if omitted).

        Returns:
            Dict with comment info.
        """
        owner = owner or self._owner
        repo = repo or self._repo
        if not owner or not repo:
            raise ValueError("owner and repo are required (set in config or pass explicitly)")

        resp = await self._request(
            "POST",
            f"/repos/{owner}/{repo}/issues/{pr_number}/comments",
            json={"body": body},
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "id": data.get("id"),
            "url": data.get("html_url", ""),
            "created_at": data.get("created_at", ""),
        }

    # --- CLI command implementations ---

    async def github_issues(self, state: str = "open", labels: list[str] | None = None, limit: int = 30) -> str:
        """CLI command: list and display open issues.

        Args:
            state: Filter by state (open/closed/all).
            labels: Optional labels to filter by.
            limit: Max issues to show.

        Returns:
            Formatted string of issues.
        """
        try:
            issues = await self.list_issues(state=state, labels=labels, limit=limit)
        except Exception as exc:
            return f"Error listing issues: {exc}"

        if not issues:
            return "No issues found."

        lines = [f"GitHub Issues ({state}, showing {len(issues)}):"]
        lines.append("-" * 60)
        for issue in issues:
            label_str = f" [{', '.join(issue['labels'])}]" if issue["labels"] else ""
            lines.append(f"  #{issue['number']} {issue['title']}{label_str}\n     {issue['url']}")
        return "\n".join(lines)

    async def github_pr_info(self, pr_number: int) -> str:
        """CLI command: display pull request details.

        Args:
            pr_number: Pull request number.

        Returns:
            Formatted string with PR info.
        """
        try:
            pr = await self.get_pull_request(pr_number)
        except Exception as exc:
            return f"Error fetching PR #{pr_number}: {exc}"

        merged_str = " (merged)" if pr["merged"] else ""
        lines = [
            f"PR #{pr['number']}: {pr['title']}{merged_str}",
            f"  State: {pr['state']}",
            f"  Author: {pr['user']}",
            f"  Branch: {pr['head']} -> {pr['base']}",
            f"  Changes: +{pr['additions']} -{pr['deletions']}",
            f"  URL: {pr['url']}",
        ]
        return "\n".join(lines)

    async def github_create_issue(
        self,
        title: str,
        body: str = "",
        labels: list[str] | None = None,
        assignees: list[str] | None = None,
    ) -> str:
        """CLI command: create a new issue.

        Args:
            title: Issue title.
            body: Issue body.
            labels: Optional labels.
            assignees: Optional assignees.

        Returns:
            Confirmation string.
        """
        try:
            result = await self.create_issue(title=title, body=body, labels=labels, assignees=assignees)
            return f"Issue created: #{result['number']} {result['title']} — {result['url']}"
        except Exception as exc:
            return f"Error creating issue: {exc}"

    # --- Lifecycle hook handlers ---

    async def _on_pre_develop(self, **kwargs: Any) -> dict[str, Any]:
        """Hook: before development starts — log context info."""
        owner = self._owner
        repo = self._repo
        return {
            "plugin": "github",
            "hook": "pre_develop",
            "repo": f"{owner}/{repo}" if owner and repo else "not-configured",
            "message": "GitHub context available for development session",
        }

    async def _on_post_develop(self, **kwargs: Any) -> dict[str, Any]:
        """Hook: after development ends — summary placeholder."""
        return {
            "plugin": "github",
            "hook": "post_develop",
            "message": "Development session complete; no GitHub action taken",
        }

    async def _on_pre_review(self, **kwargs: Any) -> dict[str, Any]:
        """Hook: before review — fetch open issues that may be relevant."""
        issues: list[dict[str, Any]] = []
        try:
            if self._owner and self._repo:
                issues = await self.list_issues(state="open", limit=10)
        except Exception as exc:
            logger.warning("Could not fetch open issues for review: %s", exc)

        return {
            "plugin": "github",
            "hook": "pre_review",
            "open_issues": issues,
            "issue_count": len(issues),
        }

    # --- Internal helpers ---

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Make an authenticated GitHub API request.

        Args:
            method: HTTP method (GET, POST, PATCH, etc.).
            path: API path (e.g., "/repos/owner/repo/issues").
            params: Optional query parameters.
            json: Optional JSON body.

        Returns:
            httpx.Response.

        Raises:
            RuntimeError: If the plugin is not initialized.
        """
        if self._client is None:
            raise RuntimeError("GitHub plugin not initialized. Call initialize() first.")

        try:
            resp = await self._client.request(method, path, params=params, json=json)
            resp.raise_for_status()
            return resp
        except httpx.HTTPStatusError as exc:
            logger.error(
                "GitHub API error %d for %s %s: %s",
                exc.response.status_code,
                method,
                path,
                exc.response.text[:200],
            )
            raise
        except httpx.RequestError as exc:
            logger.error("GitHub API request failed for %s %s: %s", method, path, exc)
            raise
