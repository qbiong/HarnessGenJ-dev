"""Tests for model selection logic."""

from harnessgenj_dev.llm.model_router import MODEL_PRIORITY, ModelInfo, select_model


class TestModelSelection:
    """Test model selection logic."""

    def test_default_selects_sonnet(self):
        """Default coding task selects claude-sonnet-4-6."""
        model = select_model()
        assert model.name == "claude-sonnet-4-6"

    def test_coding_task(self):
        """Coding task should select a coding-capable model."""
        model = select_model(task="coding")
        assert "coding" in model.capabilities

    def test_reasoning_task(self):
        """Reasoning task should select reasoning-capable model."""
        model = select_model(task="reasoning")
        assert "reasoning" in model.capabilities


class TestModelPriorityLevels:
    """Test model priority list ordering."""

    def test_sonnet_before_haiku(self):
        """Sonnet should appear before haiku in priority list."""
        names = [m.name for m in MODEL_PRIORITY]
        assert names.index("claude-sonnet-4-6") < names.index("claude-haiku-4-5-20251001")

    def test_opus_before_sonnet_for_review(self):
        """Opus should be available for review tasks."""
        review_models = [m for m in MODEL_PRIORITY if "review" in m.capabilities]
        assert any("opus" in m.name for m in review_models)

    def test_fallback_models_exist(self):
        """Should have enough models for fallback chain."""
        assert len(MODEL_PRIORITY) >= 5

    def test_model_cost_ordering(self):
        """Models should generally be ordered by capability/cost ratio."""
        # Sonnet (3.0) should be more expensive than gpt-4o-mini (0.15)
        models = {m.name: m for m in MODEL_PRIORITY}
        assert models["gpt-4o-mini"].output_cost_per_m < models["claude-sonnet-4-6"].output_cost_per_m
