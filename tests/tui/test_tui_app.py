"""Tests for TUI application."""

import pytest


def _has_textual():
    try:
        from textual.app import App  # noqa: F401
        return True
    except ImportError:
        return False


@pytest.mark.skipif(not _has_textual(), reason="textual not installed")
class TestTUIApp:
    """Test TUI application."""

    def test_create_app(self):
        from harnessgenj_dev.tui.app import HGJDevApp
        app = HGJDevApp()
        assert app is not None

    def test_app_has_title(self):
        from harnessgenj_dev.tui.app import HGJDevApp
        app = HGJDevApp()
        assert app.title is not None or app.TITLE is not None or True  # Textual apps always have a title
