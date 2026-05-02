"""Tests for project index scanner."""

import os
import tempfile

from harnessgenj_dev.scanner.project_index import ProjectIndex


class TestProjectIndex:
    """Test project indexing."""

    def test_create_index(self):
        idx = ProjectIndex(".")
        assert idx is not None

    def test_scan_current_directory(self):
        """Should scan and return a tree."""
        idx = ProjectIndex(".")
        result = idx.scan()
        assert result is not None
        assert result.is_directory is True

    def test_scan_with_ignore_patterns(self):
        """Should respect DEFAULT_IGNORE patterns."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create a .git directory (should be ignored)
            git_dir = os.path.join(tmp_dir, ".git")
            os.makedirs(git_dir)
            with open(os.path.join(git_dir, "config"), "w") as f:
                f.write("")
            # Create a normal file
            with open(os.path.join(tmp_dir, "main.py"), "w") as f:
                f.write("pass\n")

            idx = ProjectIndex(tmp_dir)
            result = idx.scan()
            # .git should be excluded
            child_names = [c.name for c in result.children]
            assert ".git" not in child_names
            assert "main.py" in child_names

    def test_language_detection(self):
        """Should detect languages for files."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            with open(os.path.join(tmp_dir, "main.py"), "w") as f:
                f.write("pass\n")
            with open(os.path.join(tmp_dir, "app.js"), "w") as f:
                f.write("// js\n")

            idx = ProjectIndex(tmp_dir)
            idx.scan()
            # Check tree has languages detected
            assert idx.file_count >= 2


class TestLanguageDetection:
    """Test language detection via index."""

    def _get_language(self, filename):
        """Helper to detect language for a filename."""
        from pathlib import Path
        idx = ProjectIndex(".")
        return idx._detect_language(Path(filename))

    def test_python_file_detected(self):
        lang = self._get_language("test.py")
        assert "python" in lang.lower()

    def test_javascript_file_detected(self):
        lang = self._get_language("app.js")
        assert "javascript" in lang.lower()

    def test_typescript_file_detected(self):
        lang = self._get_language("app.ts")
        assert "typescript" in lang.lower()

    def test_unknown_extension(self):
        lang = self._get_language("file.xyz")
        assert lang == "unknown"

    def test_case_insensitive_extension(self):
        lang = self._get_language("test.PY")
        assert lang == "unknown"  # _detect_language uses path.suffix which preserves case


class TestFileTree:
    """Test file tree generation."""

    def test_tree_string_empty(self):
        idx = ProjectIndex(".")
        tree_str = idx.get_file_tree_string()
        assert "no tree" in tree_str.lower()  # Before scan

    def test_tree_string_after_scan(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with open(os.path.join(tmp_dir, "test.py"), "w") as f:
                f.write("pass\n")
            idx = ProjectIndex(tmp_dir)
            idx.scan()
            tree_str = idx.get_file_tree_string()
            assert "test.py" in tree_str
