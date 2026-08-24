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

    log_level: str = "INFO"


class ApiSettings(RuntimeSettings):
    """Settings for the public Cafe Collection HTTP API."""

    level_bot_api_base_url: str = "http://host.docker.internal:8000"
    external_api_key: SecretStr = SecretStr("")
    cors_origins: str = "https://chill-cafe.site"

    @field_validator("level_bot_api_base_url")
    @classmethod
    def level_bot_api_base_url_must_be_http(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("LEVEL_BOT_API_BASE_URL must be an HTTP(S) URL")
        return normalized

    @property
    def allowed_cors_origins(self) -> list[str]:
        """Return the explicitly configured browser origins."""
        return [
            origin.strip() for origin in self.cors_origins.split(",") if origin.strip()
        ]


class BotSettings(RuntimeSettings):
    discord_token: SecretStr
    level_bot_api_base_url: str
    level_bot_api_token: SecretStr

    @field_validator("discord_token")
    @classmethod
    def discord_token_must_not_be_empty(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("DISCORD_TOKEN must be set when the bot is enabled")
        return value

    @field_validator("level_bot_api_base_url")
    @classmethod
    def level_bot_api_base_url_must_be_http(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("LEVEL_BOT_API_BASE_URL must be an HTTP(S) URL")
        return normalized

    @field_validator("level_bot_api_token")
    @classmethod
    def level_bot_api_token_must_not_be_empty(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("LEVEL_BOT_API_TOKEN must be set when the bot is enabled")
        return value
