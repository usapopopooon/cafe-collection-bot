import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

from cafe_collection.assets import manifest_sha256
from cafe_collection.bot import CafeCollectionBot, create_bot
from cafe_collection.level_api import CafeApiClient


def _capabilities() -> dict[str, object]:
    return {
        "api_version": 4,
        "catalog_size": 493,
        "asset_count": 495,
        "asset_manifest_sha256": manifest_sha256(),
        "paid_draw_cost_xp": 20,
        "hourly_draw_limit": 10,
        "minimum_draw_reward_xp": 25,
        "maximum_draw_reward_xp": 5000,
        "draw_reward_xp_by_rarity": {
            "C": 25,
            "UC": 30,
            "R": 60,
            "SR": 150,
            "SSR": 500,
            "UR": 1500,
            "MYTHIC": 5000,
        },
        "exchange_xp_by_rarity": {
            "C": 5,
            "UC": 10,
            "R": 20,
            "SR": 50,
            "SSR": 150,
            "UR": 500,
            "MYTHIC": 1500,
        },
        "ranking_category_totals": {},
        "set_count": 53,
    }


async def test_create_bot_uses_only_required_intents() -> None:
    bot = create_bot()
    try:
        assert isinstance(bot, CafeCollectionBot)
        assert bot.intents.guilds is True
        assert bot.intents.moderation is True
        assert bot.intents.members is False
        assert bot.intents.message_content is False
    finally:
        await bot.close()


async def test_bot_readiness_tracks_discord_connection(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    marker = tmp_path / "discord.ready"
    monkeypatch.setenv("BOT_READINESS_FILE", str(marker))
    level_api_available = True

    def handler(_request: httpx.Request) -> httpx.Response:
        if not level_api_available:
            return httpx.Response(503)
        return httpx.Response(200, json=_capabilities())

    api = CafeApiClient(
        "https://level.example.com",
        "cafe-secret",
        transport=httpx.MockTransport(handler),
    )
    bot = create_bot(api)
    try:
        await bot._probe_level_api()
        assert marker.exists() is False

        await bot.on_ready()
        assert marker.exists() is True

        level_api_available = False
        await bot._probe_level_api()
        assert marker.exists() is False

        level_api_available = True
        await bot._probe_level_api()
        assert marker.exists() is True

        await bot.on_disconnect()
        assert marker.exists() is False

        await bot.on_resumed()
        assert marker.exists() is True
    finally:
        await bot.close()

    assert marker.exists() is False


async def test_setup_installs_commands_only_for_matching_api_and_assets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_capabilities())

    api = CafeApiClient(
        "https://level.example.com",
        "cafe-secret",
        transport=httpx.MockTransport(handler),
    )
    bot = create_bot(api)
    load_extension = AsyncMock()
    sync = AsyncMock(return_value=[])
    monkeypatch.setattr(bot, "load_extension", load_extension)
    monkeypatch.setattr(bot.tree, "sync", sync)
    try:
        await bot.setup_hook()
    finally:
        await bot.close()

    load_extension.assert_awaited_once_with("cafe_collection.cog")
    sync.assert_awaited_once_with()


async def test_setup_waits_for_temporarily_unavailable_level_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            return httpx.Response(503)
        return httpx.Response(200, json=_capabilities())

    api = CafeApiClient(
        "https://level.example.com",
        "cafe-secret",
        transport=httpx.MockTransport(handler),
    )
    bot = create_bot(api)
    load_extension = AsyncMock()
    sync = AsyncMock(return_value=[])
    sleep = AsyncMock()
    monkeypatch.setattr(bot, "load_extension", load_extension)
    monkeypatch.setattr(bot.tree, "sync", sync)
    monkeypatch.setattr(asyncio, "sleep", sleep)
    try:
        await bot.setup_hook()
    finally:
        await bot.close()

    assert attempts == 3
    assert sleep.await_count == 2
    load_extension.assert_awaited_once_with("cafe_collection.cog")
    sync.assert_awaited_once_with()


async def test_setup_does_not_retry_incompatible_level_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    incompatible = _capabilities()
    incompatible["api_version"] = 3
    api = CafeApiClient(
        "https://level.example.com",
        "cafe-secret",
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json=incompatible)
        ),
    )
    bot = create_bot(api)
    sleep = AsyncMock()
    monkeypatch.setattr(asyncio, "sleep", sleep)
    try:
        with pytest.raises(RuntimeError, match="Unsupported level-bot Cafe API"):
            await bot.setup_hook()
    finally:
        await bot.close()

    sleep.assert_not_awaited()
