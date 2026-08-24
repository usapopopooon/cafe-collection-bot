"""Runtime settings."""

from __future__ import annotations

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RuntimeSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://cafe:cafe@localhost:5432/cafe_collection"
    log_level: str = "INFO"


class BotSettings(RuntimeSettings):
    discord_token: SecretStr

    @field_validator("discord_token")
    @classmethod
    def discord_token_must_not_be_empty(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("DISCORD_TOKEN must be set when the bot is enabled")
        return value
