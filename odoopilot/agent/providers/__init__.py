from __future__ import annotations

from odoopilot.agent.providers.anthropic import AnthropicProvider
from odoopilot.agent.providers.base import BaseLLMProvider
from odoopilot.agent.providers.groq import GroqProvider
from odoopilot.agent.providers.ollama import OllamaProvider
from odoopilot.agent.providers.openai import OpenAIProvider
from odoopilot.config import Settings

PROVIDER_REGISTRY: dict[str, type[BaseLLMProvider]] = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "ollama": OllamaProvider,
    "groq": GroqProvider,
}


def build_llm_provider(settings: Settings) -> BaseLLMProvider:
    """Construct the configured LLM provider from settings."""
    provider_name = settings.llm_provider

    if provider_name == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        return OpenAIProvider(
            api_key=settings.openai_api_key.get_secret_value(),
            model=settings.llm_model or "gpt-4o",
            base_url=settings.openai_base_url,
        )

    if provider_name == "anthropic":
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic")
        return AnthropicProvider(
            api_key=settings.anthropic_api_key.get_secret_value(),
            model=settings.llm_model or "claude-sonnet-4-6",
        )

    if provider_name == "ollama":
        return OllamaProvider(
            base_url=settings.ollama_base_url,
            model=settings.llm_model or settings.ollama_model,
        )

    if provider_name == "groq":
        if not settings.groq_api_key:
            raise ValueError("GROQ_API_KEY is required when LLM_PROVIDER=groq")
        return GroqProvider(
            api_key=settings.groq_api_key.get_secret_value(),
            model=settings.llm_model or settings.groq_model,
        )

    raise ValueError(f"Unknown LLM provider: {provider_name!r}")


__all__ = ["build_llm_provider", "PROVIDER_REGISTRY", "BaseLLMProvider"]
