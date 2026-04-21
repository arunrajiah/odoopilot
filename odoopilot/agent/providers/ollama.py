"""Ollama provider — self-hosted LLMs via Ollama's OpenAI-compatible API."""

from __future__ import annotations

from odoopilot.agent.providers.openai import OpenAIProvider

_DEFAULT_MODEL = "llama3.1"


class OllamaProvider(OpenAIProvider):
    """Ollama provider using its OpenAI-compatible /v1 endpoint."""

    def __init__(
        self, base_url: str = "http://localhost:11434", model: str = _DEFAULT_MODEL
    ) -> None:
        super().__init__(
            api_key="ollama",  # Ollama doesn't require a key but the SDK demands a non-empty string
            model=model,
            base_url=f"{base_url.rstrip('/')}/v1",
        )
