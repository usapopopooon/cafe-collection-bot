import pytest

from cafe_collection.config import Settings


def test_settings_reads_discord_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISCORD_TOKEN", "test-token")

    settings = Settings()  # type: ignore[call-arg]

    assert settings.discord_token.get_secret_value() == "test-token"
    assert settings.log_level == "INFO"
