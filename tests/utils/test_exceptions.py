"""Tests for custom exceptions."""
import pytest
from harnessgenj_dev.utils.exceptions import (
    HGJDevError,
    LLMError,
    ToolError,
    ConfigurationError,
    SecurityError,
    ContextOverflowError,
)


class TestHGJDevError:
    """Test base exception."""

    def test_base_error(self):
        err = HGJDevError("test error")
        assert str(err) == "test error"

    def test_inherits_from_exception(self):
        err = HGJDevError("test")
        assert isinstance(err, Exception)


class TestLLMError:
    """Test LLM exception."""

    def test_llm_error(self):
        err = LLMError("API call failed")
        assert isinstance(err, HGJDevError)


class TestToolError:
    """Test tool exception."""

    def test_tool_error(self):
        err = ToolError("Tool execution failed")
        assert isinstance(err, HGJDevError)


class TestConfigurationError:
    """Test configuration exception."""

    def test_config_error(self):
        err = ConfigurationError("Invalid config")
        assert isinstance(err, HGJDevError)


class TestSecurityError:
    """Test security exception."""

    def test_security_error(self):
        err = SecurityError("Dangerous pattern detected")
        assert isinstance(err, HGJDevError)


class TestContextOverflowError:
    """Test context overflow exception."""

    def test_overflow_error(self):
        err = ContextOverflowError("Context too large")
        assert isinstance(err, HGJDevError)
