"""Tests for enhanced Web Dashboard features."""

import json
import os
import tempfile

import pytest


def _has_fastapi():
    try:
        import fastapi  # noqa: F401
        return True
    except ImportError:
        return False


pytestmark = pytest.mark.skipif(not _has_fastapi(), reason="fastapi not installed")


@pytest.mark.asyncio
class TestEnhancedStatusEndpoint:
    """Test enhanced /api/status endpoint with metrics."""

    async def test_status_has_metrics(self):
        from harnessgenj_dev.web.dashboard import create_app
        from httpx import AsyncClient, ASGITransport

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "running"
            assert "metrics" in data
            assert "platform" in data["metrics"]
            assert "python_version" in data["metrics"]
            assert "uptime_seconds" in data["metrics"]


@pytest.mark.asyncio
class TestProjectsAPI:
    """Test project management REST API."""

    async def test_list_projects_empty(self):
        from harnessgenj_dev.web.dashboard import create_app
        from httpx import AsyncClient, ASGITransport

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/projects")
            assert resp.status_code == 200
            data = resp.json()
            assert "projects" in data
            assert "active" in data

    async def test_add_project(self):
        from harnessgenj_dev.web.dashboard import create_app
        from httpx import AsyncClient, ASGITransport

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/projects",
                json={"name": "test-app", "path": "/tmp/test-app"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["name"] == "test-app"
            assert data["path"] == "/tmp/test-app"

    async def test_add_project_missing_fields(self):
        from harnessgenj_dev.web.dashboard import create_app
        from httpx import AsyncClient, ASGITransport

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/projects", json={"name": "x"})
            assert resp.status_code == 400

    async def test_switch_project_not_found(self):
        from harnessgenj_dev.web.dashboard import create_app
        from httpx import AsyncClient, ASGITransport

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/projects/nonexistent/switch")
            assert resp.status_code == 404

    async def test_delete_project_not_found(self):
        from harnessgenj_dev.web.dashboard import create_app
        from httpx import AsyncClient, ASGITransport

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.delete("/api/projects/nonexistent")
            assert resp.status_code == 404


@pytest.mark.asyncio
class TestFileBrowserAPI:
    """Test file browser REST API."""

    async def test_list_root_files(self):
        from harnessgenj_dev.web.dashboard import create_app, set_file_root
        from httpx import AsyncClient, ASGITransport

        app = create_app()
        set_file_root(os.getcwd())
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/files")
            assert resp.status_code == 200
            data = resp.json()
            assert "items" in data
            assert "path" in data

    async def test_list_nonexistent_path(self):
        from harnessgenj_dev.web.dashboard import create_app
        from httpx import AsyncClient, ASGITransport

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/files", params={"path": "/nonexistent_xyz"})
            assert resp.status_code == 200
            data = resp.json()
            assert "error" in data

    async def test_read_file_content(self):
        from harnessgenj_dev.web.dashboard import create_app, set_file_root
        from httpx import AsyncClient, ASGITransport

        app = create_app()
        set_file_root(os.getcwd())
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/files/content", params={"path": "CLAUDE.md"}
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "content" in data or "error" in data

    async def test_read_file_no_path(self):
        from harnessgenj_dev.web.dashboard import create_app
        from httpx import AsyncClient, ASGITransport

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/files/content")
            assert resp.status_code == 200
            data = resp.json()
            assert "error" in data

    async def test_search_files(self):
        from harnessgenj_dev.web.dashboard import create_app, set_file_root
        from httpx import AsyncClient, ASGITransport

        app = create_app()
        set_file_root(os.getcwd())
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/files/search", params={"path": "tests", "pattern": "*.py"}
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "matches" in data
            assert "pattern" in data


class TestHTMLPages:
    """Test HTML page rendering."""

    @pytest.mark.asyncio
    async def test_projects_page(self):
        from harnessgenj_dev.web.dashboard import create_app
        from httpx import AsyncClient, ASGITransport

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/projects")
            assert resp.status_code == 200
            assert "text/html" in resp.headers.get("content-type", "")
            assert "Projects" in resp.text

    @pytest.mark.asyncio
    async def test_files_page(self):
        from harnessgenj_dev.web.dashboard import create_app
        from httpx import AsyncClient, ASGITransport

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/files")
            assert resp.status_code == 200
            assert "text/html" in resp.headers.get("content-type", "")
            assert "File Browser" in resp.text


class TestFileRootSecurity:
    """Test file root security."""

    def test_safe_path_traversal(self):
        """Path traversal should be prevented."""
        from harnessgenj_dev.web.dashboard import _safe_path, _file_root, set_file_root

        # Set root to current working directory
        set_file_root(os.getcwd())

        # Try to traverse above root
        from fastapi import HTTPException

        with pytest.raises(HTTPException):
            _safe_path("../../etc/passwd")

    def test_set_file_root(self):
        """Test setting file root."""
        from harnessgenj_dev.web.dashboard import set_file_root
        from pathlib import Path

        set_file_root("/tmp")
        from harnessgenj_dev.web.dashboard import _file_root as new_root
        # On Windows, /tmp becomes C:/tmp
        assert str(new_root).endswith("tmp")
        # Reset
        set_file_root(os.getcwd())
