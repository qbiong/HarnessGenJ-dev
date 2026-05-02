"""Tests for scanner module."""


def test_project_index_scan(temp_dir):
    """Test project index scanning."""
    from harnessgenj_dev.scanner.project_index import ProjectIndex

    # Create some test files
    (temp_dir / "main.py").write_text("print('hello')", encoding="utf-8")
    (temp_dir / "sub").mkdir()
    (temp_dir / "sub" / "utils.py").write_text("def foo(): pass", encoding="utf-8")

    index = ProjectIndex(root=str(temp_dir))
    tree = index.scan()

    assert tree.is_directory
    assert index.file_count == 2


def test_language_detection():
    """Test programming language detection."""
    from harnessgenj_dev.scanner.project_index import ProjectIndex

    index = ProjectIndex()
    from pathlib import Path

    assert index._detect_language(Path("test.py")) == "python"
    assert index._detect_language(Path("test.go")) == "go"
    assert index._detect_language(Path("test.rs")) == "rust"
    assert index._detect_language(Path("test.unknown")) == "unknown"
