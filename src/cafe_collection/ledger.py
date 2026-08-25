"""Public Cafe ledger delivery owned by the Cafe Collection bot."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Literal

import discord
from discord.ext import commands

from cafe_collection.assets import card_image_path
from cafe_collection.level_api import (
    CafeApiClient,
    CafeDraw,
    CafeLedgerDrawBatch,
    CafeLedgerRedemption,
)
from cafe_collection.presentation import CAFE_COLLECTION_SITE_URL

logger = logging.getLogger(__name__)
COLLECTION_SIZE = 463
RARITY_ORDER = ("C", "UC", "R", "SR", "SSR", "UR", "MYTHIC")
RARITY_LABELS = {
    "C": "N",
    "UC": "HN",
    "R": "R",
    "SR": "SR",
    "SSR": "SSR",
    "UR": "UR",
    "MYTHIC": "幻",
}
PUBLIC_MENTION_RARITIES = {"R", "SR", "SSR", "UR", "MYTHIC"}
_guild_locks: dict[int, asyncio.Lock] = {}
type LedgerRecord = CafeLedgerDrawBatch | CafeLedgerRedemption
type LedgerRecordType = Literal["draw", "redemption"]


def _notification_nonce(record_type: str, event_id: str) -> int:
    digest = hashlib.blake2b(
        f"cafe:collection-bot:{record_type}:{event_id}".encode(), digest_size=8
    ).digest()
    return int.from_bytes(digest, "big") & ((1 << 63) - 1)


def _rarity_label(rarity: str) -> str:
    return RARITY_LABELS.get(rarity, rarity)


def _draw_embed(
    draw: CafeDraw,
    *,
    user_id: str,
    attachment_filename: str | None,
    batch_slot: int | None,
) -> discord.Embed:
    colors = {
        "C": 0x8B7D6B,
        "UC": 0x5FA36A,
        "R": 0x4C83C3,
        "SR": 0xA659C5,
        "SSR": 0xD6A72C,
        "UR": 0xA8325A,
        "MYTHIC": 0x62469B,
    }
    collection_state = " · 重複" if draw.was_duplicate else ""
    cost = "無料" if draw.draw_type == "free" else f"{draw.cost_xp:,} XP消費"
    exchange_bonus = (
        f"\n♻️ 重複カードは交換すると **さらに +{draw.exchange_xp:,} XP！**"
        if draw.was_duplicate
        else ""
    )
    card_url = f"{CAFE_COLLECTION_SITE_URL}cards/{draw.reward_key}/"
    if batch_slot is not None:
        card_url = f"{card_url}?batch_slot={batch_slot}"
    embed = discord.Embed(
        title=f"{_rarity_label(draw.rarity)}｜{draw.reward_name}",
        url=card_url,
        description=(
            f"**<@{user_id}> さんが一枚引きました**\n\n{draw.reward_description}"
        ),
        color=colors[draw.rarity],
    )
    embed.add_field(
        name=f"🎉 +{draw.reward_xp - draw.cost_xp:,} XPの黒字！",
        value=(f"{cost} → {draw.reward_xp:,} XP獲得{collection_state}{exchange_bonus}"),
        inline=False,
    )
    collection_progress = (
        f"収集 **{max(0, draw.collected_count - 1)} → "
        f"{draw.collected_count}/{COLLECTION_SIZE}種**"
        if not draw.was_duplicate
        else f"収集 {draw.collected_count}/{COLLECTION_SIZE}種"
    )
    embed.add_field(
        name="📚 コレクション",
        value=(
            f"所持 {draw.owned_count}枚 · 交換可能 "
            f"{max(0, draw.owned_count - 1)}枚\n{collection_progress}"
        ),
        inline=False,
    )
    if attachment_filename is not None:
        embed.set_image(url=f"attachment://{attachment_filename}")
    if draw.rarity == "MYTHIC":
        embed.set_footer(text="🔮 存在しないはずの秘宝がカフェに現れました")
    elif draw.rarity == "UR":
        embed.set_footer(text="📜 歴史に残る一品がカフェに並びました")
    elif draw.rarity in ("SR", "SSR"):
        embed.set_footer(text="✨ カフェに珍しい一枚が並びました")
    return embed


def _highest_rarity(draws: list[CafeDraw]) -> str:
    return max(draws, key=lambda item: RARITY_ORDER.index(item.rarity)).rarity


def _batch_summary(batch: CafeLedgerDrawBatch) -> str:
    total_cost = sum(draw.cost_xp for draw in batch.draws)
    total_reward = sum(draw.reward_xp for draw in batch.draws)
    return (
        f"☕ **{len(batch.draws)}枚まとめ引き**｜最高 "
        f"**{_rarity_label(_highest_rarity(batch.draws))}**\n"
        f"{total_cost:,} XP消費 → {total_reward:,} XP獲得 "
        f"（差引 **+{total_reward - total_cost:,} XP**）"
    )


def _safe_card_name(name: str) -> str:
    return discord.utils.escape_mentions(discord.utils.escape_markdown(name))


def _draw_mention(batch: CafeLedgerDrawBatch) -> str | None:
    mentioned = [
        draw.rarity for draw in batch.draws if draw.rarity in PUBLIC_MENTION_RARITIES
    ]
    new_draws = [draw for draw in batch.draws if not draw.was_duplicate]
    if not mentioned and not new_draws:
        return None
    lines: list[str] = []
    if mentioned:
        highest = max(mentioned, key=RARITY_ORDER.index)
        notice = (
            "幻のカード"
            if highest == "MYTHIC"
            else f"{_rarity_label(highest)}以上のカード"
        )
        lines.append(f"🎉 <@{batch.user_id}>さん、{notice}を獲得しました！")
    elif len(new_draws) == 1:
        lines.append(f"✨ <@{batch.user_id}>さん、新しいカードを獲得しました！")
    else:
        lines.append(
            f"✨ <@{batch.user_id}>さん、コレクションに新しいカードが "
            f"**{len(new_draws)}枚** 加わりました！"
        )
    if new_draws:
        names = "／".join(_safe_card_name(draw.reward_name) for draw in new_draws)
        if len(new_draws) == 1:
            prefix = "✨" if mentioned else "📚"
            lines.append(f"{prefix} **{names}**がコレクションに加わりました！")
        else:
            if mentioned:
                lines.append(
                    f"✨ コレクションに新しいカードが **{len(new_draws)}枚** "
                    "加わりました！"
                )
            lines.append(f"📚 **{names}**")
    return "\n".join(lines)


def _redemption_embed(redemption: CafeLedgerRedemption) -> discord.Embed:
    detail = "、".join(
        f"{item.reward_name}×{item.quantity}" for item in redemption.items
    )
    if len(detail) > 3000:
        lines: list[str] = []
        for rarity in RARITY_ORDER:
            rarity_items = [item for item in redemption.items if item.rarity == rarity]
            if rarity_items:
                lines.append(
                    f"{_rarity_label(rarity)}: {len(rarity_items)}種・合計"
                    f"{sum(item.quantity for item in rarity_items)}枚"
                )
        detail = "全カードの重複を一括交換\n" + "\n".join(lines)
    return discord.Embed(
        title="♻️ 重複カード交換でXPボーナス！",
        description=(
            f"**<@{redemption.user_id}> さんが交換しました**\n\n"
            f"{detail}\n\n"
            f"**🎉 +{redemption.reward_xp:,} XPを追加獲得！**"
        ),
        color=0x57F287,
    )


async def _find_message(
    channel: discord.TextChannel,
    *,
    bot_user_id: int,
    record_type: str,
    event_id: str,
    created_at: datetime,
) -> discord.Message | None:
    nonce = str(_notification_nonce(record_type, event_id))
    async for message in channel.history(
        limit=None, after=created_at - timedelta(minutes=1)
    ):
        if message.author.id == bot_user_id and str(message.nonce) == nonce:
            return message
    return None


async def _publish_draw_batch(
    channel: discord.TextChannel,
    *,
    bot_user_id: int,
    batch: CafeLedgerDrawBatch,
) -> str | None:
    message = await _find_message(
        channel,
        bot_user_id=bot_user_id,
        record_type="draw-batch",
        event_id=batch.event_id,
        created_at=batch.created_at,
    )
    if message is None:
        files: list[discord.File] = []
        embeds: list[discord.Embed] = []
        try:
            for draw in batch.draws:
                image_path = card_image_path(draw.reward_key)
                image_matches = (
                    image_path is not None and image_path.name == draw.image_filename
                )
                if len(batch.draws) > 1 and not image_matches:
                    raise OSError(f"missing Cafe image for {draw.reward_key}")
                filename = (
                    (
                        f"{draw.batch_position:02d}-{draw.image_filename}"
                        if len(batch.draws) > 1
                        else draw.image_filename
                    )
                    if image_matches
                    else None
                )
                if image_path is not None and filename is not None:
                    files.append(discord.File(image_path, filename=filename))
                embed = _draw_embed(
                    draw,
                    user_id=batch.user_id,
                    attachment_filename=filename,
                    batch_slot=draw.batch_position if len(batch.draws) > 1 else None,
                )
                if len(batch.draws) > 1:
                    embed.title = (
                        f"☕ {len(batch.draws)}枚まとめ "
                        f"{draw.batch_position}/{len(batch.draws)}｜"
                        f"{_rarity_label(draw.rarity)}｜{draw.reward_name}"
                    )
                embeds.append(embed)
            message = await channel.send(
                content=_batch_summary(batch) if len(batch.draws) > 1 else None,
                embeds=embeds,
                files=files,
                nonce=_notification_nonce("draw-batch", batch.event_id),
                allowed_mentions=discord.AllowedMentions.none(),
            )
        finally:
            for file in files:
                file.close()
    mention = _draw_mention(batch)
    if mention is not None:
        mention_message = await _find_message(
            channel,
            bot_user_id=bot_user_id,
            record_type="draw-mention",
            event_id=batch.event_id,
            created_at=batch.created_at,
        )
        if mention_message is None:
            await channel.send(
                mention,
                nonce=_notification_nonce("draw-mention", batch.event_id),
                allowed_mentions=discord.AllowedMentions(
                    everyone=False,
                    users=[discord.Object(id=int(batch.user_id))],
                    roles=False,
                    replied_user=False,
                ),
            )
    return str(message.id)


async def _publish_redemption(
    channel: discord.TextChannel,
    *,
    bot_user_id: int,
    redemption: CafeLedgerRedemption,
) -> str:
    message = await _find_message(
        channel,
        bot_user_id=bot_user_id,
        record_type="redemption",
        event_id=redemption.event_id,
        created_at=redemption.created_at,
    )
    if message is None:
        message = await channel.send(
            embed=_redemption_embed(redemption),
            nonce=_notification_nonce("redemption", redemption.event_id),
            allowed_mentions=discord.AllowedMentions.none(),
        )
    return str(message.id)


async def _resolve_ledger_channel(
    bot: commands.Bot, guild: discord.Guild, channel_id: str
) -> discord.TextChannel | None:
    channel = guild.get_channel(int(channel_id))
    if channel is None:
        try:
            fetched_channel = await bot.fetch_channel(int(channel_id))
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return None
        return (
            fetched_channel
            if isinstance(fetched_channel, discord.TextChannel)
            else None
        )
    return channel if isinstance(channel, discord.TextChannel) else None


async def publish_pending_for_guild(
    bot: commands.Bot,
    api: CafeApiClient,
    guild: discord.Guild,
) -> set[tuple[LedgerRecordType, str]]:
    """Post every unhandled transaction to this bot's configured ledger."""
    bot_user = bot.user
    if bot_user is None:
        return set()
    delivered: set[tuple[LedgerRecordType, str]] = set()
    lock = _guild_locks.setdefault(guild.id, asyncio.Lock())
    async with lock:
        pending = await api.pending_ledger(guild_id=str(guild.id))
        if pending.ledger_channel_id is None:
            return delivered
        channel = await _resolve_ledger_channel(bot, guild, pending.ledger_channel_id)
        if channel is None:
            return delivered
        records: list[tuple[datetime, LedgerRecordType, LedgerRecord]] = []
        records.extend(
            (batch.created_at, "draw", batch) for batch in pending.draw_batches
        )
        records.extend(
            (redemption.created_at, "redemption", redemption)
            for redemption in pending.redemptions
        )
        records.sort(key=lambda item: item[0])
        for _created_at, record_type, record in records:
            try:
                if record_type == "draw":
                    assert isinstance(record, CafeLedgerDrawBatch)
                    message_id = await _publish_draw_batch(
                        channel, bot_user_id=bot_user.id, batch=record
                    )
                else:
                    assert isinstance(record, CafeLedgerRedemption)
                    message_id = await _publish_redemption(
                        channel, bot_user_id=bot_user.id, redemption=record
                    )
                if message_id is not None:
                    await api.mark_ledger_delivered(
                        guild_id=str(guild.id),
                        record_type=record_type,
                        event_id=record.event_id,
                        message_id=message_id,
                    )
                    delivered.add((record_type, record.event_id))
            except (discord.HTTPException, OSError):
                logger.exception(
                    "Failed to publish Cafe %s %s to guild %s ledger",
                    record_type,
                    record.event_id,
                    guild.id,
                )
    return delivered
