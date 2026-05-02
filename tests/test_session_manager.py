"""Tests for the SessionManager."""

import json
import tempfile
from pathlib import Path

import pytest

from harnessgenj_dev.web.session_manager import Session, SessionManager


@pytest.fixture
def tmp_session_dir():
    """Create a temporary directory for session storage."""
    with tempfile.TemporaryDirectory() as td:
        yield td


@pytest.fixture
def mgr(tmp_session_dir):
    """Create a SessionManager with a temp directory."""
    return SessionManager(base_dir=tmp_session_dir)


class TestSession:
    """Test Session dataclass."""

    def test_create_session(self):
        s = Session(id="abc123", project="test")
        assert s.id == "abc123"
        assert s.project == "test"
        assert s.role == "product_manager"
        assert s.messages == []
        assert s.message_count == 0

    def test_add_message(self):
        s = Session(id="abc", project="test")
        s.add_message("user", "hello")
        assert s.message_count == 1
        assert s.messages[0]["role"] == "user"
        assert s.messages[0]["content"] == "hello"

    def test_clear(self):
        s = Session(id="abc", project="test")
        s.add_message("user", "hello")
        s.add_message("assistant", "hi")
        s.clear()
        assert s.message_count == 0

    def test_to_dict_from_dict(self):
        s = Session(id="abc", project="test", role="developer")
        s.add_message("user", "test")
        d = s.to_dict()
        s2 = Session.from_dict(d)
        assert s2.id == s.id
        assert s2.project == s.project
        assert s2.role == s.role
        assert s2.message_count == s.message_count

    def test_session_title_empty(self):
        s = Session(id="abc", project="test")
        assert SessionManager._session_title(s) == "New conversation"

    def test_session_title_from_message(self):
        s = Session(id="abc", project="test")
        s.add_message("user", "Build a web scraper")
        assert SessionManager._session_title(s) == "Build a web scraper"

    def test_session_title_truncated(self):
        s = Session(id="abc", project="test")
        s.add_message("user", "A" * 100)
        title = SessionManager._session_title(s)
        assert len(title) == 83  # 80 + "..."
        assert title.endswith("...")


class TestSessionManager:
    """Test SessionManager."""

    def test_create_session(self, mgr):
        s = mgr.create_session("myproject", role="developer")
        assert s.project == "myproject"
        assert s.role == "developer"
        assert s.id is not None

    def test_create_session_saves_to_disk(self, mgr, tmp_session_dir):
        s = mgr.create_session("myproject")
        project_dir = Path(tmp_session_dir) / "myproject"
        session_file = project_dir / f"{s.id}.json"
        assert session_file.exists()
        data = json.loads(session_file.read_text())
        assert data["id"] == s.id

    def test_get_session(self, mgr):
        s = mgr.create_session("myproject")
        found = mgr.get_session("myproject", s.id)
        assert found is not None
        assert found.id == s.id

    def test_get_session_not_found(self, mgr):
        found = mgr.get_session("myproject", "nonexistent")
        assert found is None

    def test_get_active_session_creates_if_none(self, mgr):
        s = mgr.get_active_session("newproject")
        assert s is not None
        assert s.project == "newproject"

    def test_list_sessions(self, mgr):
        mgr.create_session("proj", role="developer")
        mgr.create_session("proj", role="reviewer")
        mgr.create_session("proj", role="architect")
        sessions = mgr.list_sessions("proj")
        assert len(sessions) == 3

    def test_list_sessions_sorted_by_updated(self, mgr):
        mgr.create_session("proj")
        mgr.create_session("proj")
        sessions = mgr.list_sessions("proj")
        # Most recently updated first
        assert sessions[0]["updated_at"] >= sessions[1]["updated_at"]

    def test_delete_session(self, mgr):
        s = mgr.create_session("proj")
        assert mgr.delete_session("proj", s.id) is True
        assert mgr.get_session("proj", s.id) is None

    def test_delete_session_clears_active(self, mgr):
        s = mgr.create_session("proj")
        mgr.delete_session("proj", s.id)
        # After deleting the only session, no new session is auto-created
        sessions = mgr.list_sessions("proj")
        assert len(sessions) == 0

    def test_switch_session(self, mgr):
        s1 = mgr.create_session("proj")
        s2 = mgr.create_session("proj")
        assert mgr.switch_session("proj", s1.id) is True

    def test_switch_session_not_found(self, mgr):
        mgr.create_session("proj")
        assert mgr.switch_session("proj", "nonexistent") is False

    def test_save_session(self, mgr):
        s = mgr.create_session("proj")
        s.add_message("user", "hello")
        mgr.save(s)
        # Reload from disk
        s2 = mgr.get_session("proj", s.id)
        assert s2 is not None
        assert s2.message_count == 1

    def test_session_persistence_across_instances(self, mgr, tmp_session_dir):
        """Sessions should survive recreating the manager."""
        s = mgr.create_session("proj")
        s.add_message("user", "persistent data")
        mgr.save(s)

        # Create new manager instance
        mgr2 = SessionManager(base_dir=tmp_session_dir)
        found = mgr2.get_session("proj", s.id)
        assert found is not None
        assert found.message_count == 1
        assert found.messages[0]["content"] == "persistent data"

    def test_active_session_file(self, mgr, tmp_session_dir):
        s = mgr.create_session("proj")
        active_file = Path(tmp_session_dir) / "proj" / "active.json"
        assert active_file.exists()
        data = json.loads(active_file.read_text())
        assert data["session_id"] == s.id

    def test_project_name_sanitization(self, mgr, tmp_session_dir):
        """Project names with slashes should be sanitized."""
        mgr.create_session("my/deep/project")
        project_dir = Path(tmp_session_dir) / "my_deep_project"
        assert project_dir.exists()

    def test_list_sessions_with_limit(self, mgr):
        for i in range(10):
            mgr.create_session("proj")
        sessions = mgr.list_sessions("proj", limit=3)
        assert len(sessions) == 3
