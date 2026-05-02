"""Custom exception definitions."""

from __future__ import annotations


class HGJDevError(Exception):
    """Base exception for HarnessGenJ-dev."""


class LLMError(HGJDevError):
    """Error during LLM communication."""


class ToolError(HGJDevError):
    """Error during tool execution."""


class ConfigurationError(HGJDevError):
    """Error in configuration."""


class SecurityError(HGJDevError):
    """Security violation detected."""


class ContextOverflowError(HGJDevError):
    """Context window overflow."""
