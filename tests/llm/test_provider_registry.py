"""Tests for provider registry management."""
from harnessgenj_dev.llm.gateway import LLMGateway, _PROVIDER_REGISTRY
from harnessgenj_dev.llm.providers.base import BaseProvider


class TestProviderRegistration:
    """Test custom provider registration."""

    def test_register_custom_provider(self):
        gw = LLMGateway()

        class DummyProvider(BaseProvider):
            @property
            def provider_name(self):
                return "dummy"

            async def chat(self, **kwargs):
                pass

            async def stream(self, **kwargs):
                pass

        gw.register_provider("dummy", DummyProvider())
        assert "dummy" in _PROVIDER_REGISTRY

    def test_provider_registry_has_builtins(self):
        assert "anthropic" in _PROVIDER_REGISTRY
        assert "openai" in _PROVIDER_REGISTRY
