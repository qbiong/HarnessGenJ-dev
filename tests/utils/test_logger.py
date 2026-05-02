"""Tests for logger utility."""
from harnessgenj_dev.utils.logger import get_logger
import logging


class TestLogger:
    """Test logger functionality."""

    def test_get_logger(self):
        logger = get_logger("test_module")
        assert logger is not None
        assert logger.name == "test_module"

    def test_logger_level(self):
        logger = get_logger("test_level")
        assert isinstance(logger.level, int)

    def test_logger_has_handlers(self):
        logger = get_logger("test_handlers")
        assert len(logger.handlers) > 0

    def test_logger_can_log(self):
        logger = get_logger("test_can_log")
        logger.info("Test message")
        assert logger.isEnabledFor(logging.INFO)

    def test_logger_debug_level(self):
        logger = get_logger("test_debug")
        assert logger.isEnabledFor(logging.WARNING)
