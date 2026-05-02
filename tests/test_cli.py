"""Tests for CLI entry point and commands."""

import sys
from unittest.mock import patch, MagicMock

import pytest

from harnessgenj_dev.cli import main, _cmd_init, _cmd_status


class TestMainEntry:
    """Test main() entry point."""

    def test_main_version_flag(self, capsys):
        with patch.object(sys, "argv", ["hgj-dev", "--version"]):
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 0
        captured = capsys.readouterr()
        assert "0.1.0" in captured.out

    def test_main_no_command_shows_help(self, capsys):
        with patch.object(sys, "argv", ["hgj-dev"]):
            main()
        captured = capsys.readouterr()
        assert "usage" in captured.out.lower() or "hgj-dev" in captured.out

    def test_main_unknown_command(self):
        with patch.object(sys, "argv", ["hgj-dev", "nonexistent"]):
            with pytest.raises(SystemExit) as exc:
                main()
            # argparse exits with code 2 for invalid choices
            assert exc.value.code == 2

    def test_main_help_command(self, capsys):
        with patch.object(sys, "argv", ["hgj-dev", "help"]):
            main()
        captured = capsys.readouterr()
        assert "usage" in captured.out.lower() or "hgj-dev" in captured.out


class TestCmdInit:
    """Test _cmd_init function."""

    def test_init_creates_config(self, tmp_path, monkeypatch):
        # _cmd_init takes argparse.Namespace, not kwargs
        import shutil
        from pathlib import Path
        config_dir = Path.home() / ".hgj-dev"
        config_file = config_dir / "config.yaml"
        # Clean up existing config to ensure test isolation
        if config_file.exists():
            config_file.unlink()

        args = MagicMock()
        args.path = str(tmp_path)

        result = _cmd_init(args)
        assert result == 0
        assert config_file.exists()

        # Clean up
        if config_file.exists():
            config_file.unlink()

    def test_init_config_already_exists(self, tmp_path, monkeypatch):
        args = MagicMock()
        args.path = str(tmp_path)

        # First call succeeds
        _cmd_init(args)
        # Second call should fail (config exists)
        result = _cmd_init(args)
        assert result == 1

    def test_init_save_failure(self, monkeypatch):
        from harnessgenj_dev import config as config_module
        original_save = config_module.AppConfig.save

        def failing_save(self, path=None):
            raise PermissionError("Cannot write")

        config_module.AppConfig.save = failing_save
        try:
            args = MagicMock()
            args.path = "/tmp"
            result = _cmd_init(args)
            assert result == 1
        finally:
            config_module.AppConfig.save = original_save


class TestCmdStatus:
    """Test _cmd_status function."""

    def test_status_basic(self, capsys):
        args = MagicMock()
        result = _cmd_status(args)
        assert isinstance(result, int)


class TestBanner:
    """Test _print_banner function."""

    def test_print_banner(self, capsys):
        from harnessgenj_dev.cli import _print_banner
        _print_banner()
        captured = capsys.readouterr()
        assert "HarnessGenJ" in captured.out
