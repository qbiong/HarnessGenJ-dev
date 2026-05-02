"""Tests for web dashboard."""

import pytest


def _has_fastapi():
    try:
        import fastapi  # noqa: F401
        return True
    except ImportError:
        return False


pytestmark = pytest.mark.skipif(not _has_fastapi(), reason="fastapi not installed")


class TestConnectionManager:
    """Test ConnectionManager functionality."""

    def test_create_manager(self):
        from harnessgenj_dev.web.dashboard import ConnectionManager
        mgr = ConnectionManager()
        assert mgr is not None
        assert mgr.active_connections == []


class TestDashboardApp:
    """Test FastAPI application structure."""

    def test_create_app(self):
        from harnessgenj_dev.web.dashboard import create_app
        app = create_app()
        assert app is not None
        assert app.title == "HGJ-dev Dashboard"

    def test_app_has_routes(self):
        from harnessgenj_dev.web.dashboard import create_app
        app = create_app()
        routes = [r.path for r in app.routes]
        assert "/" in routes
        assert "/ws" in routes
        assert "/api/status" in routes
        assert "/api/plugins" in routes


@pytest.mark.asyncio
class TestDashboardEndpoints:
    """Test dashboard HTTP endpoints."""

    async def test_status_endpoint(self):
        """Status endpoint should return running state."""
        from harnessgenj_dev.web.dashboard import create_app
        from httpx import AsyncClient, ASGITransport

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "running"
            assert "version" in data
            assert "active_connections" in data

    async def test_plugins_endpoint(self):
        """Plugins endpoint should return list."""
        from harnessgenj_dev.web.dashboard import create_app
        from httpx import AsyncClient, ASGITransport

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/plugins")
            assert resp.status_code == 200
            data = resp.json()
            assert "plugins" in data

    async def test_dashboard_page(self):
        """Dashboard page should return HTML."""
        from harnessgenj_dev.web.dashboard import create_app
        from httpx import AsyncClient, ASGITransport

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/")
            assert resp.status_code == 200
            assert "text/html" in resp.headers.get("content-type", "")
            assert "HGJ-dev" in resp.text
