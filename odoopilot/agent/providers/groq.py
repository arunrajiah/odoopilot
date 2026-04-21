"""Groq provider — fast inference via Groq's OpenAI-compatible API."""

from __future__ import annotations

from odoopilot.agent.providers.openai import OpenAIProvider

_DEFAULT_MODEL = "llama-3.1-70b-versatile"
_GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class GroqProvider(OpenAIProvider):
    """Groq provider using its OpenAI-compatible API."""

    def __init__(self, api_key: str, model: str = _DEFAULT_MODEL) -> None:
        super().__init__(api_key=api_key, model=model, base_url=_GROQ_BASE_URL)
