"""Tests for system prompt builder (agent-based)."""

from harnessgenj_dev.core.agent import Agent


class TestSystemPrompt:
    """Test system prompt construction via Agent."""

    def test_build_developer_prompt(self):
        """Developer role should produce valid prompt."""
        agent = Agent()
        prompt = agent._build_system_prompt(role="developer")
        assert "clean, tested, production-ready code" in prompt

    def test_build_reviewer_prompt(self):
        """Code reviewer role should produce valid prompt."""
        agent = Agent()
        prompt = agent._build_system_prompt(role="code_reviewer")
        assert "review" in prompt.lower() or "Review" in prompt

    def test_prompt_includes_tools(self):
        """Prompt should include tool information when tools registered."""
        from harnessgenj_dev.tools.registry import auto_register
        auto_register()
        agent = Agent()
        prompt = agent._build_system_prompt(role="developer")
        assert "Available Tools" in prompt or "tool" in prompt.lower()

    def test_prompt_includes_rules(self):
        """Prompt should include rules section."""
        agent = Agent()
        prompt = agent._build_system_prompt(role="developer")
        assert "Rules" in prompt or "rules" in prompt.lower()

    def test_all_roles_produce_prompt(self):
        """All roles should produce non-empty prompts."""
        agent = Agent()
        for role in ["developer", "code_reviewer", "bug_hunter", "architect", "product_manager", "doc_writer"]:
            prompt = agent._build_system_prompt(role=role)
            assert prompt, f"Empty prompt for role: {role}"

    def test_unknown_role_uses_default(self):
        """Unknown role should use default instructions."""
        agent = Agent()
        prompt = agent._build_system_prompt(role="unknown_role_xyz")
        assert prompt  # Should not crash
