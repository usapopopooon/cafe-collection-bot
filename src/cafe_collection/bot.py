"""Discord bot composition root."""

from __future__ import annotations

import logging

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class CafeCollectionBot(commands.Bot):
    """Bot shell that will receive Cafe Collection extensions during migration."""

    async def setup_hook(self) -> None:
        logger.info("Cafe Collection extensions are not installed yet")

    async def on_ready(self) -> None:
        if self.user is not None:
            logger.info("Logged in as %s (ID: %s)", self.user, self.user.id)


def create_bot() -> CafeCollectionBot:
    """Create the inactive Cafe Collection bot shell."""
    intents = discord.Intents.default()
    intents.guilds = True
    intents.members = True
    return CafeCollectionBot(command_prefix="!", intents=intents)
