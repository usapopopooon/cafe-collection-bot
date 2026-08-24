"""Application entry point."""

from __future__ import annotations

import logging

from cafe_collection.bot import create_bot
from cafe_collection.config import Settings


def main() -> None:
    settings = Settings()  # type: ignore[call-arg]
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    create_bot().run(settings.discord_token.get_secret_value())
