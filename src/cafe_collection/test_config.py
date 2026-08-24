import pytest
from pydantic import ValidationError

from cafe_collection.config import ApiSettings, BotSettings, RuntimeSettings


def test_settings_reads_discord_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISCORD_TOKEN", "test-token")
    monkeypatch.setenv("LEVEL_BOT_API_BASE_URL", "https://level.example.com/")
    monkeypatch.setenv("LEVEL_BOT_API_TOKEN", "api-token")

    settings = BotSettings()  # type: ignore[call-arg]

    assert settings.discord_token.get_secret_value() == "test-token"
    assert settings.level_bot_api_base_url == "https://level.example.com"
    assert settings.level_bot_api_token.get_secret_value() == "api-token"
    assert settings.log_level == "INFO"


def test_runtime_settings_have_log_level_default() -> None:
    settings = RuntimeSettings()

    assert settings.log_level == "INFO"


def test_api_settings_parse_level_bot_url_and_cors_origins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LEVEL_BOT_API_BASE_URL", "https://level.example.com/")
    monkeypatch.setenv("EXTERNAL_API_KEY", "shared-public-jwt")
    monkeypatch.setenv(
        "CORS_ORIGINS",
        "https://chill-cafe.site, https://preview.example.com",
    )

    settings = ApiSettings()

    assert settings.level_bot_api_base_url == "https://level.example.com"
    assert settings.external_api_key.get_secret_value() == "shared-public-jwt"
    assert settings.allowed_cors_origins == [
        "https://chill-cafe.site",
        "https://preview.example.com",
    ]


def test_bot_settings_reject_empty_discord_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DISCORD_TOKEN", "")
    monkeypatch.setenv("LEVEL_BOT_API_BASE_URL", "https://level.example.com")
    monkeypatch.setenv("LEVEL_BOT_API_TOKEN", "api-token")

    with pytest.raises(ValidationError, match="DISCORD_TOKEN must be set"):
        BotSettings()  # type: ignore[call-arg]


def test_bot_settings_reject_missing_level_api_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DISCORD_TOKEN", "test-token")
    monkeypatch.setenv("LEVEL_BOT_API_BASE_URL", "https://level.example.com")
    monkeypatch.setenv("LEVEL_BOT_API_TOKEN", "")

    with pytest.raises(ValidationError, match="LEVEL_BOT_API_TOKEN must be set"):
        BotSettings()  # type: ignore[call-arg]
