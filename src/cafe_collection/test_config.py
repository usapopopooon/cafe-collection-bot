import pytest
from pydantic import ValidationError

from cafe_collection.config import BotSettings, RuntimeSettings


def test_settings_reads_discord_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISCORD_TOKEN", "test-token")

    settings = BotSettings()  # type: ignore[call-arg]

    assert settings.discord_token.get_secret_value() == "test-token"
    assert settings.log_level == "INFO"


def test_runtime_settings_have_local_database_default() -> None:
    settings = RuntimeSettings()

    assert settings.database_url.endswith("@localhost:5432/cafe_collection")


def test_bot_settings_reject_empty_discord_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DISCORD_TOKEN", "")

    with pytest.raises(ValidationError, match="DISCORD_TOKEN must be set"):
        BotSettings()  # type: ignore[call-arg]
