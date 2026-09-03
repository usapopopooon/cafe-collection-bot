from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast

import discord
import httpx
import pytest
from discord.ext import commands

from cafe_collection import ledger
from cafe_collection.level_api import CafeApiClient, CafeDraw, CafeLedgerDrawBatch


class _Message:
    def __init__(
        self,
        *,
        message_id: int,
        author_id: int,
        content: str,
        nonce: int | None,
        embeds: list[discord.Embed],
    ) -> None:
        self.id = message_id
        self.author = SimpleNamespace(id=author_id)
        self.content = content
        self.nonce = nonce
        self.embeds = embeds


class _Channel:
    def __init__(self, *, bot_user_id: int) -> None:
        self.bot_user_id = bot_user_id
        self.messages: list[_Message] = []
        self.attachment_filenames: list[list[str]] = []

    async def send(self, content: str | None = None, **kwargs: Any) -> _Message:
        message = _Message(
            message_id=7000 + len(self.messages),
            author_id=self.bot_user_id,
            content=content or "",
            nonce=kwargs.get("nonce"),
            embeds=(
                kwargs.get("embeds", [])
                or ([kwargs["embed"]] if kwargs.get("embed") is not None else [])
            ),
        )
        self.attachment_filenames.append(
            [file.filename for file in kwargs.get("files", [])]
        )
        self.messages.append(message)
        return message

    def history(self, *, limit: int | None, after: datetime) -> AsyncIterator[_Message]:
        async def _iterate() -> AsyncIterator[_Message]:
            for message in reversed(self.messages):
                yield message

        return _iterate()


async def test_new_bot_posts_and_recovers_its_own_draw_and_redemption_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delivered_payloads: list[dict[str, object]] = []
    created_at = datetime(2026, 8, 24, 1, 0, tzinfo=UTC).isoformat()
    pending_payload = {
        "ledger_channel_id": "3002",
        "draw_batches": [
            {
                "event_id": "one-transaction",
                "user_id": "2001",
                "created_at": created_at,
                "draws": [
                    {
                        "event_id": "one-transaction",
                        "batch_position": 1,
                        "reward_key": "100-yen-black-tea",
                        "reward_name": "麦茶",
                        "reward_description": "香ばしい一杯。",
                        "rarity": "C",
                        "image_filename": "100-yen-black-tea.jpg",
                        "draw_type": "free",
                        "cost_xp": 0,
                        "reward_xp": 10,
                        "exchange_xp": 5,
                        "was_duplicate": False,
                        "owned_count": 1,
                        "collected_count": 1,
                    }
                ],
            }
        ],
        "redemptions": [
            {
                "event_id": "one-redemption",
                "user_id": "2001",
                "created_at": created_at,
                "reward_xp": 5,
                "items": [
                    {
                        "reward_key": "100-yen-black-tea",
                        "reward_name": "麦茶",
                        "rarity": "C",
                        "quantity": 1,
                        "reward_per_card": 5,
                        "reward_total": 5,
                    }
                ],
            }
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/ledger/pending"):
            return httpx.Response(200, json=pending_payload)
        delivered_payloads.append(cast(dict[str, object], json.loads(request.content)))
        return httpx.Response(200, json={"delivered": True})

    api = CafeApiClient(
        "https://level.example.com",
        "cafe-secret",
        transport=httpx.MockTransport(handler),
    )
    channel = _Channel(bot_user_id=9001)

    async def resolve_channel(
        _bot: commands.Bot, _guild: discord.Guild, _channel_id: str
    ) -> discord.TextChannel:
        return cast(discord.TextChannel, channel)

    monkeypatch.setattr(ledger, "_resolve_ledger_channel", resolve_channel)
    bot = cast(commands.Bot, SimpleNamespace(user=SimpleNamespace(id=9001)))
    guild = cast(discord.Guild, SimpleNamespace(id=1001))
    try:
        await ledger.publish_pending_for_guild(bot, api, guild)
        await ledger.publish_pending_for_guild(bot, api, guild)
    finally:
        await api.close()

    assert len(channel.messages) == 3
    assert channel.messages[0].embeds[0].title == "N｜麦茶"
    collection_value = channel.messages[0].embeds[0].fields[1].value
    assert collection_value is not None
    assert "収集 **0 → 1/511種**" in collection_value
    assert channel.attachment_filenames[0] == ["100-yen-black-tea.jpg"]
    assert channel.messages[1].content == (
        "✨ <@2001>さん、新しいカードを獲得しました！\n"
        "📚 **麦茶**がコレクションに加わりました！"
    )
    assert channel.messages[2].embeds[0].title == ("♻️ 重複カード交換でXPボーナス！")
    assert [payload["record_type"] for payload in delivered_payloads] == [
        "draw",
        "redemption",
        "draw",
        "redemption",
    ]
    assert {str(message.nonce) for message in channel.messages} == {
        str(ledger._notification_nonce("draw-batch", "one-transaction")),
        str(ledger._notification_nonce("draw-mention", "one-transaction")),
        str(ledger._notification_nonce("redemption", "one-redemption")),
    }


async def test_single_draw_without_an_image_still_reaches_the_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ledger, "card_image_path", lambda _reward_key: None)
    channel = _Channel(bot_user_id=9001)
    batch = CafeLedgerDrawBatch(
        event_id="missing-image",
        user_id="2001",
        created_at=datetime(2026, 8, 24, 1, 0, tzinfo=UTC),
        draws=[
            CafeDraw(
                event_id="missing-image",
                batch_position=1,
                reward_key="missing-card",
                reward_name="画像なしカード",
                reward_description="説明",
                rarity="C",
                image_filename="missing-card.jpg",
                draw_type="free",
                cost_xp=0,
                reward_xp=10,
                exchange_xp=5,
                was_duplicate=True,
                owned_count=2,
                collected_count=1,
            )
        ],
    )

    message_id = await ledger._publish_draw_batch(
        cast(discord.TextChannel, channel),
        bot_user_id=9001,
        batch=batch,
    )

    assert message_id == "7000"
    assert len(channel.messages) == 1
    assert channel.attachment_filenames[0] == []
    assert channel.messages[0].embeds[0].image.url is None
