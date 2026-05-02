"""Tests for TUI module."""

import pytest


def _has_textual() -> bool:
    """Check if textual is available."""
    try:
        import textual  # noqa: F401
        return True
    except ImportError:
        return False


@pytest.mark.skipif(
    not _has_textual(),
    reason="textual not installed",
)
def test_tui_app_exists():
    """Test that TUI module is importable."""
    from harnessgenj_dev.tui import app

    assert hasattr(app, "run_app")
    assert hasattr(app, "HGJDevApp")
