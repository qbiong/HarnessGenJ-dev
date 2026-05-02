"""Tests for ContextManager - Claude Code style three-tier compaction."""

import pytest

from harnessgenj_dev.core.context_manager import (
    CompactionResult,
    ContextManager,
    get_context_manager,
)


class TestContextManager:
    """Test Claude Code style three-tier context compaction."""

    def test_create_manager(self):
        mgr = ContextManager()
        assert mgr is not None
        assert mgr.max_tokens == 1000000
        assert mgr.compaction_threshold == 0.90
        assert mgr.tier1_keep_results == 10

    def test_custom_parameters(self):
        mgr = ContextManager(max_tokens=100000, compaction_threshold=0.7)
        assert mgr.max_tokens == 100000
        assert mgr.compaction_threshold == 0.70

    def test_threshold_tokens(self):
        mgr = ContextManager(max_tokens=100000, compaction_threshold=0.8)
        assert mgr.threshold_tokens == 80000

    def test_get_usage_ratio_empty(self):
        mgr = ContextManager()
        ratio = mgr.get_usage_ratio([])
        assert ratio == 0.0

    def test_get_usage_ratio(self):
        mgr = ContextManager(max_tokens=100000)
        messages = [
            {"role": "user", "content": "Hello world " * 100},
            {"role": "assistant", "content": "Hi there " * 100},
        ]
        ratio = mgr.get_usage_ratio(messages)
        assert ratio > 0

    def test_needs_compaction_below_threshold(self):
        mgr = ContextManager(max_tokens=100000)
        messages = [{"role": "user", "content": "test"}]
        assert mgr.needs_compaction(messages) is False

    def test_needs_compaction_at_threshold(self):
        mgr = ContextManager(max_tokens=1000, compaction_threshold=0.8)
        # Create enough content to exceed threshold
        messages = [
            {"role": "user", "content": "x" * 5000},
        ]
        # This should trigger compaction check
        ratio = mgr.get_usage_ratio(messages)
        assert ratio > 0


class TestTier1MicroCompact:
    """Test Tier 1: Micro-compact - clean old tool results."""

    def test_no_tool_results(self):
        mgr = ContextManager()
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]
        result = mgr.tier1_micro_compact(messages)
        assert result.tier_applied == 1
        assert result.tool_results_truncated == 0

    def test_keeps_recent_tool_results(self):
        mgr = ContextManager(tier1_keep_results=3)
        # Create 10 tool results
        messages = []
        for i in range(10):
            messages.append({
                "role": "tool",
                "content": f"Tool result {i}",
                "tool_call_id": f"call_{i}",
            })

        result = mgr.tier1_micro_compact(messages)

        assert result.tool_results_truncated == 7
        assert result.tier_applied == 1
        # Check that recent 3 are kept
        assert "Tool result 7" in messages[7]["content"]
        assert "Tool result 8" in messages[8]["content"]
        assert "Tool result 9" in messages[9]["content"]

    def test_old_tool_results_truncated(self):
        mgr = ContextManager(tier1_keep_results=2)
        # Need more than keep_results to trigger truncation
        messages = [
            {"role": "tool", "content": f"Result {i}", "tool_call_id": f"call_{i}"}
            for i in range(5)
        ]

        result = mgr.tier1_micro_compact(messages)

        assert result.tool_results_truncated == 3
        # First 3 should be truncated
        assert "truncated" in messages[0]["content"].lower()
        assert "truncated" in messages[1]["content"].lower()
        assert "truncated" in messages[2]["content"].lower()
        # Last 2 should be kept
        assert messages[3]["content"] == "Result 3"
        assert messages[4]["content"] == "Result 4"


class TestTier2APIScompact:
    """Test Tier 2: API-level compaction - compress older messages."""

    def test_under_recent_count(self):
        mgr = ContextManager()
        messages = [
            {"role": "user", "content": f"Message {i}"}
            for i in range(10)
        ]
        result = mgr.tier2_api_compact(messages)
        assert result.tier_applied == 2
        # Should keep all when under recent_count
        assert len(messages) == 10

    def test_compresses_old_messages(self):
        mgr = ContextManager()
        messages = [
            {"role": "user", "content": f"Old message {i}"}
            for i in range(30)
        ]

        result = mgr.tier2_api_compact(messages)

        assert result.messages_removed > 0
        assert result.tier_applied == 2
        # Should have system message with summary
        system_msgs = [m for m in messages if m.get("role") == "system"]
        assert len(system_msgs) > 0
        assert "Compacted" in system_msgs[0].get("content", "")


class TestTier3FullSummarize:
    """Test Tier 3: Full LLM summarization."""

    def test_creates_summary_structure(self):
        mgr = ContextManager()
        messages = [
            {"role": "user", "content": "Build a web scraper"},
            {"role": "assistant", "content": "I'll help you build a web scraper."},
            {"role": "tool", "content": "File created: scraper.py"},
            {"role": "user", "content": "Add error handling"},
        ]

        result = mgr.tier3_full_summarize(messages)

        assert result.tier_applied == 3
        assert result.messages_removed > 0
        # Tier 3 creates a new summary message, preserving metadata
        assert "COMPACTION BOUNDARY" in result.summary or "Intent" in result.summary


class TestMainCompress:
    """Test main compress entry point."""

    def test_force_tier_1(self):
        mgr = ContextManager()
        messages = [
            {"role": "tool", "content": "x" * 1000}
            for _ in range(10)
        ]
        result = mgr.compress(messages, force_tier=1)
        assert result.tier_applied == 1

    def test_force_tier_2(self):
        mgr = ContextManager()
        messages = [
            {"role": "user", "content": f"Message {i}"}
            for i in range(30)
        ]
        result = mgr.compress(messages, force_tier=2)
        assert result.tier_applied == 2

    def test_force_tier_3(self):
        mgr = ContextManager()
        messages = [
            {"role": "user", "content": "Build something"},
            {"role": "assistant", "content": "I'll build it."},
        ]
        result = mgr.compress(messages, force_tier=3)
        assert result.tier_applied == 3


class TestRebuildContext:
    """Test context rebuild after compaction."""

    def test_rebuild_basic(self):
        mgr = ContextManager()
        summary = "## 1. Intent\nUser wanted to build a web scraper"
        recent_files = [{"path": "scraper.py", "content": "import requests"}]
        skills = ["skill1", "skill2"]
        tool_schemas = [{"function": {"name": "read_file"}}]
        claude_md = "# Project Rules\nWrite clean code"

        result = mgr.rebuild_context(summary, recent_files, skills, tool_schemas, claude_md)

        assert len(result) > 0
        assert result[0]["role"] == "system"
        assert "COMPACTION BOUNDARY" in result[0]["content"]


class TestGetContextManager:
    """Test global instance getter."""

    def test_returns_same_instance(self):
        mgr1 = get_context_manager()
        mgr2 = get_context_manager()
        assert mgr1 is mgr2