"""Local model provider.

Supports locally hosted LLM servers that expose an OpenAI-compatible API,
including:
- Ollama (default: http://localhost:11434/v1)
- vLLM
- llama.cpp server
- LocalAI
- LM Studio

All of these use the OpenAI SDK with a custom base URL.
"""

from __future__ import annotations

from typing import Any

from .openai import OpenAIProvider

DEFAULT_OLLAMA_URL = "http://localhost:11434/v1"
DEFAULT_VLLM_URL = "http://localhost:8000/v1"


class LocalProvider(OpenAIProvider):
    """Local model server adapter.

    Inherits from OpenAIProvider since local servers (Ollama, vLLM, etc.)
    expose an OpenAI-compatible API. Only the base URL and usage parsing
    differ.
    """

    def __init__(
        self,
        api_key: str = "",
        base_url: str | None = None,
        backend: str = "ollama",
    ) -> None:
        """Initialize local model client.

        Args:
            api_key: API key (usually not needed for local servers).
            base_url: Server URL. Auto-selects default based on backend.
            backend: Server type ('ollama', 'vllm', 'llamacpp', 'localai', 'lmstudio').
        """
        if base_url is None:
            if backend == "vllm":
                base_url = DEFAULT_VLLM_URL
            else:
                base_url = DEFAULT_OLLAMA_URL

        super().__init__(api_key=api_key or "not-needed", base_url=base_url)
        self.backend = backend

    @property
    def provider_name(self) -> str:
        return "local"

    def _build_usage(self, usage: Any) -> Any:
        """Build UsageReport from local server usage.

        Local models typically don't have real cost, so we set
        estimated_cost to 0 but track token counts.
        """
        from ..models import UsageReport

        input_tokens = getattr(usage, "prompt_tokens", 0)
        output_tokens = getattr(usage, "completion_tokens", 0)
        total = getattr(usage, "total_tokens", input_tokens + output_tokens)

        return UsageReport(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total,
            estimated_cost=0.0,  # Local models have no API cost
        )
