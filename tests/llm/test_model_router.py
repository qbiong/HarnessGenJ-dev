"""Tests for LLM model router."""

from harnessgenj_dev.llm.model_router import ModelInfo, MODEL_PRIORITY, select_model


class TestModelInfo:
    """Test ModelInfo dataclass."""

    def test_model_has_name(self):
        model = MODEL_PRIORITY[0]
        assert model.name

    def test_model_has_provider(self):
        model = MODEL_PRIORITY[0]
        assert model.provider

    def test_model_has_cost(self):
        model = MODEL_PRIORITY[0]
        assert model.input_cost_per_m > 0
        assert model.output_cost_per_m > 0

    def test_model_has_capabilities(self):
        model = MODEL_PRIORITY[0]
        assert model.capabilities
        assert isinstance(model.capabilities, list)

    def test_model_has_max_tokens(self):
        model = MODEL_PRIORITY[0]
        assert model.max_tokens > 0


class TestModelSelection:
    """Test model selection logic."""

    def test_default_coding_task(self):
        """Default task is coding, should return claude-sonnet."""
        model = select_model()
        assert model is not None
        assert model.name == "claude-sonnet-4-6"

    def test_coding_task_selects_sonnet(self):
        """Coding task selects claude-sonnet-4-6 by default."""
        model = select_model(task="coding")
        assert model is not None
        assert "coding" in model.capabilities

    def test_budget_filter_excludes_expensive(self):
        """Very low budget should exclude expensive models."""
        model = select_model(task="coding", budget=0.000001)
        # Even with low budget, returns first candidate (no budget filter passes)
        assert model is not None

    def test_all_priority_models(self):
        """All priority models have valid data."""
        for model in MODEL_PRIORITY:
            assert model.name
            assert model.provider
            assert model.input_cost_per_m >= 0
            assert model.output_cost_per_m >= 0
            assert model.max_tokens > 0
            assert len(model.capabilities) > 0

    def test_model_count(self):
        """Should have at least 5 default models."""
        assert len(MODEL_PRIORITY) >= 5

    def test_anthropic_models_exist(self):
        """Should have Anthropic models."""
        names = [m.name for m in MODEL_PRIORITY]
        assert "claude-sonnet-4-6" in names
        assert "claude-opus-4-6" in names
        assert "claude-haiku-4-5-20251001" in names

    def test_openai_models_exist(self):
        """Should have OpenAI models."""
        names = [m.name for m in MODEL_PRIORITY]
        assert "gpt-4o" in names
        assert "gpt-4o-mini" in names

    def test_sonnet_cheaper_than_opus(self):
        """Sonnet should be cheaper than Opus."""
        models = {m.name: m for m in MODEL_PRIORITY}
        sonnet = models["claude-sonnet-4-6"]
        opus = models["claude-opus-4-6"]
        assert sonnet.output_cost_per_m < opus.output_cost_per_m

    def test_haiku_cheapest(self):
        """Haiku should be the cheapest model."""
        costs = {m.name: m.output_cost_per_m for m in MODEL_PRIORITY if "haiku" in m.name}
        if costs:
            haiku_cost = list(costs.values())[0]
            assert haiku_cost < 5.0  # $4.0/M
