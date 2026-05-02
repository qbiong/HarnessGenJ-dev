"""Tests for Local provider."""
from harnessgenj_dev.llm.providers.local import LocalProvider, DEFAULT_OLLAMA_URL, DEFAULT_VLLM_URL


class TestLocalProviderInit:
    """Test LocalProvider initialization."""

    def test_provider_name(self):
        p = LocalProvider()
        assert p.provider_name == "local"

    def test_default_ollama_url(self):
        p = LocalProvider()
        assert p.base_url == DEFAULT_OLLAMA_URL

    def test_vllm_backend(self):
        p = LocalProvider(backend="vllm")
        assert p.base_url == DEFAULT_VLLM_URL

    def test_custom_base_url(self):
        p = LocalProvider(base_url="http://my-server:9000")
        assert p.base_url == "http://my-server:9000"

    def test_backend_attribute(self):
        p = LocalProvider(backend="llamacpp")
        assert p.backend == "llamacpp"

    def test_default_backend(self):
        p = LocalProvider()
        assert p.backend == "ollama"
