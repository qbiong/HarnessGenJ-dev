"""Shared pytest fixtures."""

import os

import pytest


@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory for testing."""
    return tmp_path


@pytest.fixture
def sample_python_file(tmp_path):
    """Create a sample Python file for testing."""
    file_path = tmp_path / "sample.py"
    file_path.write_text(
        'def hello():\n    print("Hello, World!")\n\n'
        'class MyClass:\n    def __init__(self):\n        self.value = 42\n',
        encoding="utf-8",
    )
    return file_path


# ---------------------------------------------------------------------------
# API Key fixtures for real-provider end-to-end tests
# ---------------------------------------------------------------------------


@pytest.fixture
def has_anthropic_key() -> bool:
    """Whether ANTHROPIC_API_KEY is set in the environment."""
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


@pytest.fixture
def has_openai_key() -> bool:
    """Whether OPENAI_API_KEY is set in the environment."""
    return bool(os.environ.get("OPENAI_API_KEY", "").strip())


def pytest_configure(config):
    """Register custom pytest markers."""
    config.addinivalue_line(
        "markers", "e2e: end-to-end tests requiring real API keys (slow)"
    )
    config.addinivalue_line(
        "markers", "anthropic: tests requiring ANTHROPIC_API_KEY"
    )
    config.addinivalue_line(
        "markers", "openai: tests requiring OPENAI_API_KEY"
    )
    config.addinivalue_line(
        "markers", "slow: tests that take longer to run"
    )
