"""Discord bot composition root."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import discord
from discord.ext import commands, tasks

from cafe_collection.assets import manifest_sha256
from cafe_collection.ledger import publish_pending_for_guild
from cafe_collection.level_api import CafeApiClient, CafeApiError, CafeCapabilities

logger = logging.getLogger(__name__)
DEFAULT_READINESS_FILE = "/tmp/cafe-collection-bot.ready"
EXPECTED_CATALOG_SIZE = 361
EXPECTED_ASSET_COUNT = 363


def readiness_file() -> Path:
    """Return the marker used by the container health check."""
    return Path(os.environ.get("BOT_READINESS_FILE", DEFAULT_READINESS_FILE))


def write_readiness_marker(ready: bool) -> None:
    """Publish whether both Discord and the required Cafe API are available."""
    marker = readiness_file()
    if ready:
        marker.touch()
    else:
        marker.unlink(missing_ok=True)


class CafeCollectionBot(commands.Bot):
    """Bot shell that will receive Cafe Collection extensions during migration."""

    def __init__(
        self,
        *,
        intents: discord.Intents,
        cafe_api: CafeApiClient | None,
    ) -> None:
        super().__init__(command_prefix="!", intents=intents)
        self.cafe_api = cafe_api
        self._discord_ready = False
        self._level_api_ready = False

    @staticmethod
    def _validate_capabilities(capabilities: CafeCapabilities) -> None:
        if capabilities.api_version != 3:
            raise RuntimeError("Unsupported level-bot Cafe API version")
        if (
            capabilities.catalog_size != EXPECTED_CATALOG_SIZE
            or capabilities.asset_count != EXPECTED_ASSET_COUNT
        ):
            raise RuntimeError("Cafe catalog size does not match level-bot")
        if capabilities.asset_manifest_sha256 != manifest_sha256():
            raise RuntimeError("Cafe image bundle does not match level-bot")

    def _publish_readiness(self) -> None:
        write_readiness_marker(self._discord_ready and self._level_api_ready)

    async def _probe_level_api(self) -> None:
        if self.cafe_api is None:
            self._level_api_ready = False
            self._publish_readiness()
            return
        try:
            capabilities = await self.cafe_api.capabilities()
            self._validate_capabilities(capabilities)
        except (CafeApiError, OSError, RuntimeError):
            if self._level_api_ready:
                logger.warning("level-bot Cafe API health probe failed", exc_info=True)
            self._level_api_ready = False
        else:
            self._level_api_ready = True
        self._publish_readiness()

    @tasks.loop(seconds=30)
    async def level_api_health_loop(self) -> None:
        """Keep container readiness aligned with the required level-bot API."""
        await self._probe_level_api()

    @tasks.loop(minutes=5)
    async def ledger_delivery_loop(self) -> None:
        """Retry this bot's configured public ledgers independently."""
        if self.cafe_api is None:
            return
        for guild in self.guilds:
            try:
                await publish_pending_for_guild(self, self.cafe_api, guild)
            except CafeApiError:
                logger.exception(
                    "Failed to load Cafe ledger transactions for guild %s", guild.id
                )

    @ledger_delivery_loop.before_loop
    async def before_ledger_delivery_loop(self) -> None:
        await self.wait_until_ready()

    async def setup_hook(self) -> None:
        write_readiness_marker(False)
        if self.cafe_api is None:
            logger.info("Cafe Collection API client is not configured")
            return
        capabilities = await self.cafe_api.capabilities()
        self._validate_capabilities(capabilities)
        self._level_api_ready = True
        await self.load_extension("cafe_collection.cog")
        synced = await self.tree.sync()
        logger.info("Installed and synced %d Cafe commands", len(synced))
        self.level_api_health_loop.start()
        self.ledger_delivery_loop.start()

    async def on_ready(self) -> None:
        self._discord_ready = True
        self._publish_readiness()
        if self.user is not None:
            logger.info("Logged in as %s (ID: %s)", self.user, self.user.id)

    async def on_disconnect(self) -> None:
        self._discord_ready = False
        self._publish_readiness()

    async def on_resumed(self) -> None:
        self._discord_ready = True
        self._publish_readiness()

    async def close(self) -> None:
        self._discord_ready = False
        self._level_api_ready = False
        self._publish_readiness()
        self.level_api_health_loop.cancel()
        self.ledger_delivery_loop.cancel()
        if self.cafe_api is not None:
            await self.cafe_api.close()
        await super().close()


def create_bot(cafe_api: CafeApiClient | None = None) -> CafeCollectionBot:
    """Create the inactive Cafe Collection bot shell."""
    intents = discord.Intents.default()
    intents.guilds = True
    return CafeCollectionBot(intents=intents, cafe_api=cafe_api)
