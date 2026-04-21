from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Odoo connection
    odoo_url: str = Field(
        ..., description="Base URL of Odoo instance, e.g. https://odoo.example.com"
    )
    odoo_db: str = Field(..., description="Odoo database name")
    odoo_admin_user: str = Field(..., description="Odoo admin username")
    odoo_admin_password: SecretStr = Field(..., description="Odoo admin password")

    # Telegram
    telegram_bot_token: SecretStr = Field(..., description="Telegram Bot API token from @BotFather")
    telegram_webhook_url: str = Field(..., description="Public HTTPS URL for Telegram webhook")
    telegram_webhook_secret: SecretStr | None = Field(
        default=None, description="Optional secret token for webhook validation"
    )

    # LLM provider selection
    llm_provider: Literal["openai", "anthropic", "ollama", "groq"] = Field(
        default="openai", description="Which LLM provider to use"
    )
    llm_model: str | None = Field(
        default=None, description="Model name override; uses provider default if unset"
    )

    # Provider credentials
    openai_api_key: SecretStr | None = Field(default=None)
    openai_base_url: str | None = Field(default=None, description="Override for compatible APIs")

    anthropic_api_key: SecretStr | None = Field(default=None)

    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_model: str = Field(default="llama3.1")

    groq_api_key: SecretStr | None = Field(default=None)
    groq_model: str = Field(default="llama-3.1-70b-versatile")

    # Storage
    database_url: str = Field(
        default="sqlite+aiosqlite:///./odoopilot.db",
        description="SQLAlchemy async database URL",
    )

    # App
    secret_key: SecretStr = Field(
        default=SecretStr("change-me-in-production"),
        description="Secret for signing linking tokens",
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
