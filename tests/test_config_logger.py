"""Tests for logger and config edge cases."""

import os
import tempfile

import pytest

from harnessgenj_dev.utils.logger import get_logger
from harnessgenj_dev.config import (
    AppConfig,
    LLMConfig,
    ToolConfig,
    WorkflowConfig,
)


class TestLogger:
    """Test get_logger function."""

    def test_get_logger_custom_level(self):
        logger = get_logger("test_custom_level", level="DEBUG")
        assert logger.level <= 10  # DEBUG level

    def test_get_logger_no_duplicate_handlers(self):
        """Calling get_logger twice with same name should not add duplicate handlers."""
        import logging
        name = "test_no_dup"
        logger1 = get_logger(name)
        handler_count_1 = len(logger1.handlers)
        logger2 = get_logger(name)
        handler_count_2 = len(logger2.handlers)
        assert handler_count_1 == handler_count_2


class TestLLMConfig:
    """Test LLMConfig model."""

    def test_defaults(self):
        cfg = LLMConfig()
        assert cfg.provider == "anthropic"
        assert cfg.max_retries == 3
        assert cfg.retry_base_delay == 1.0
        assert cfg.retry_max_delay == 60.0

    def test_custom_values(self):
        cfg = LLMConfig(
            provider="openai",
            model="gpt-4o",
            max_retries=5,
        )
        assert cfg.provider == "openai"
        assert cfg.max_retries == 5


class TestToolConfig:
    """Test ToolConfig model."""

    def test_defaults(self):
        cfg = ToolConfig()
        assert len(cfg.enabled_tools) == 7
        assert "read_file" in cfg.enabled_tools
        assert cfg.default_timeout == 30

    def test_custom_values(self):
        cfg = ToolConfig(enabled_tools=["read_file"], max_output_chars=5000)
        assert "read_file" in cfg.enabled_tools


class TestWorkflowConfig:
    """Test WorkflowConfig model."""

    def test_defaults(self):
        cfg = WorkflowConfig()
        assert cfg.default_pipeline == "develop"

    def test_custom_values(self):
        cfg = WorkflowConfig(default_pipeline="bug_fix")
        assert cfg.default_pipeline == "bug_fix"



class TestAppConfig:
    """Test AppConfig model and persistence."""

    def test_default_config(self):
        cfg = AppConfig()
        assert cfg.llm.provider == "anthropic"
        assert len(cfg.tools.enabled_tools) == 7

    def test_save_and_load(self, tmp_path):
        config_path = str(tmp_path / "config.yaml")
        cfg = AppConfig()
        cfg.llm.provider = "openai"
        cfg.save(config_path)
        assert os.path.exists(config_path)

        loaded = AppConfig.load(config_path)
        assert loaded is not None
        assert loaded.llm.provider == "openai"

    def test_load_nonexistent_file(self):
        cfg = AppConfig.load("/nonexistent/config.yaml")
        assert cfg is not None  # Returns default AppConfig
        assert isinstance(cfg, AppConfig)

    def test_load_malformed_yaml(self, tmp_path):
        path = str(tmp_path / "bad.yaml")
        with open(path, "w") as f:
            f.write("{invalid: yaml: content: [}")

        cfg = AppConfig.load(path)
        # Malformed YAML returns default config (load catches the exception)
        assert isinstance(cfg, AppConfig)

    def test_default_config_path(self):
        path = AppConfig.default_config_path()
        from pathlib import Path
        assert isinstance(path, Path)
        assert path.name == "config.yaml"

    def test_save_creates_directory(self, tmp_path):
        config_path = str(tmp_path / "new_dir" / "config.yaml")
        cfg = AppConfig()
        cfg.save(config_path)
        assert os.path.exists(config_path)
