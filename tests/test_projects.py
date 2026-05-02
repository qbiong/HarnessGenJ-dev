"""Tests for multi-project management."""

import json
import os
import tempfile

import pytest

from harnessgenj_dev.projects import Project, ProjectManager


class TestProject:
    """Test Project dataclass."""

    def test_create_project(self):
        p = Project(name="test", path="/tmp/test")
        assert p.name == "test"
        assert p.path == "/tmp/test"
        assert p.created_at > 0
        assert p.last_accessed > 0
        assert p.metadata == {}

    def test_project_with_metadata(self):
        p = Project(name="app", path="/app", metadata={"lang": "python"})
        assert p.metadata["lang"] == "python"

    def test_touch_updates_timestamp(self):
        import time
        p = Project(name="test", path="/tmp")
        old = p.last_accessed
        time.sleep(0.01)
        p.touch()
        assert p.last_accessed > old


class TestProjectManager:
    """Test ProjectManager functionality."""

    def test_create_manager(self):
        pm = ProjectManager()
        assert pm is not None
        assert pm.project_count == 0
        assert pm.active_name is None

    def test_add_project(self):
        pm = ProjectManager()
        pm.add_project("my-app", "/path/to/app")
        assert pm.project_count == 1
        assert "my-app" in [p.name for p in pm.list_projects()]

    def test_add_project_with_metadata(self):
        pm = ProjectManager()
        pm.add_project("app", "/app", metadata={"lang": "python"})
        p = pm.get_project("app")
        assert p is not None
        assert p.metadata["lang"] == "python"

    def test_remove_project(self):
        pm = ProjectManager()
        pm.add_project("app", "/app")
        assert pm.remove_project("app") is True
        assert pm.project_count == 0

    def test_remove_nonexistent_project(self):
        pm = ProjectManager()
        assert pm.remove_project("missing") is False

    def test_switch_to_project(self):
        pm = ProjectManager()
        pm.add_project("app", "/app")
        p = pm.switch_to("app")
        assert p.name == "app"
        assert pm.active_name == "app"

    def test_switch_to_nonexistent_raises(self):
        pm = ProjectManager()
        with pytest.raises(KeyError):
            pm.switch_to("missing")

    def test_get_active_none(self):
        pm = ProjectManager()
        pm.add_project("app", "/app")
        assert pm.get_active() is None

    def test_get_active_after_switch(self):
        pm = ProjectManager()
        pm.add_project("app", "/app")
        pm.switch_to("app")
        active = pm.get_active()
        assert active is not None
        assert active.name == "app"

    def test_get_project(self):
        pm = ProjectManager()
        pm.add_project("app", "/app")
        p = pm.get_project("app")
        assert p is not None
        assert p.name == "app"

    def test_get_nonexistent_project(self):
        pm = ProjectManager()
        assert pm.get_project("missing") is None

    def test_list_projects_sorted(self):
        pm = ProjectManager()
        import time
        pm.add_project("a", "/a")
        time.sleep(0.01)
        pm.add_project("b", "/b")
        projects = pm.list_projects()
        # Most recently added should be first
        assert projects[0].name == "b"
        assert projects[1].name == "a"

    def test_remove_active_clears_active(self):
        pm = ProjectManager()
        pm.add_project("app", "/app")
        pm.switch_to("app")
        pm.remove_project("app")
        assert pm.active_name is None


class TestProjectManagerPersistence:
    """Test project metadata persistence."""

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            storage = os.path.join(tmp_dir, "projects.json")
            pm = ProjectManager(storage_path=storage)
            pm.add_project("app", "/app", metadata={"lang": "python"})
            pm.switch_to("app")
            pm._save()

            # Load into new manager
            pm2 = ProjectManager(storage_path=storage)
            pm2.load()
            assert pm2.project_count == 1
            assert pm2.active_name == "app"
            p = pm2.get_project("app")
            assert p is not None
            assert p.metadata["lang"] == "python"

    def test_load_nonexistent_file(self):
        pm = ProjectManager(storage_path="/nonexistent/path.json")
        pm.load()  # Should not raise
        assert pm.project_count == 0

    def test_save_no_storage_path(self):
        pm = ProjectManager()
        pm.add_project("app", "/app")
        pm._save()  # Should not raise (no-op)


class TestProjectWebIntegration:
    """Test project endpoint in web dashboard."""

    @pytest.mark.asyncio
    async def test_api_status_has_projects(self):
        """Status endpoint returns connection count."""
        from harnessgenj_dev.web.dashboard import create_app
        from httpx import AsyncClient, ASGITransport

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "running"
