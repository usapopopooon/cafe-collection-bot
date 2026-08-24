"""Application entry point."""

from __future__ import annotations

import logging

from cafe_collection.bot import create_bot
from cafe_collection.config import BotSettings
from cafe_collection.level_api import CafeApiClient


def main() -> None:
    settings = BotSettings()  # type: ignore[call-arg]
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    api = CafeApiClient(
        settings.level_bot_api_base_url,
        settings.level_bot_api_token.get_secret_value(),
    )
    create_bot(api).run(settings.discord_token.get_secret_value())
