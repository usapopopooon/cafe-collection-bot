"""Discord commands backed by level-bot's transactional Cafe API."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import re
from datetime import datetime, timedelta
from time import monotonic
from typing import Literal
from uuid import uuid4
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands, tasks

from cafe_collection.assets import ASSET_DIR
from cafe_collection.collection_image import RARITY_LABELS
from cafe_collection.collection_ui import show_full_collection
from cafe_collection.discord_context import (
    actor_from_interaction as _actor,
)
from cafe_collection.discord_context import (
    api_from_interaction as _api,
)
from cafe_collection.discord_context import (
    ensure_feature_access as _ensure_feature_access,
)
from cafe_collection.discord_context import (
    send_api_error as _send_api_error,
)
from cafe_collection.ledger import publish_pending_for_guild
from cafe_collection.level_api import (
    CafeActor,
    CafeApiClient,
    CafeApiError,
    CafeAvailability,
    CafeCapabilities,
    CafeCollectionCard,
    CafeDrawBatch,
    CafeRankings,
)
from cafe_collection.presentation import (
    CAFE_COLLECTION_SITE_URL,
    CAFE_RANKINGS_SITE_URL,
    CATEGORY_PRESENTATIONS,
    LEDGER_TITLE,
    PANEL_TITLE,
    RANKING_TITLE,
    build_analytics_embed,
    build_panel_embed,
    build_ranking_detail_embed,
    build_ranking_panel_embed,
)

logger = logging.getLogger(__name__)
COUNTER_NAME = "☕️カフェカウンター"
LEDGER_NAME = "📒カフェ台帳"
_setup_locks: dict[int, asyncio.Lock] = {}
_ranking_cache: dict[int, tuple[CafeRankings, float]] = {}
_ranking_viewer_cache: dict[tuple[int, str], tuple[CafeRankings, float]] = {}
_ranking_locks: dict[int, asyncio.Lock] = {}
_ranking_banned_user_ids: dict[int, set[str]] = {}
RANKING_CACHE_SECONDS = 5 * 60.0


def _clear_ranking_cache(guild_id: int) -> None:
    _ranking_cache.pop(guild_id, None)
    for key in [key for key in _ranking_viewer_cache if key[0] == guild_id]:
        _ranking_viewer_cache.pop(key, None)


def _without_known_bans(rankings: CafeRankings, guild_id: int) -> CafeRankings:
    blocked = _ranking_banned_user_ids.get(guild_id, set())
    if not blocked:
        return rankings
    categories = [
        category.model_copy(
            update={
                "entries": [
                    entry for entry in category.entries if entry.user_id not in blocked
                ],
                "viewer_entry": (
                    None
                    if category.viewer_entry is not None
                    and category.viewer_entry.user_id in blocked
                    else category.viewer_entry
                ),
            }
        )
        for category in rankings.categories
    ]
    return rankings.model_copy(update={"categories": categories})


async def _get_cached_rankings(
    api: CafeApiClient,
    actor: CafeActor,
) -> tuple[CafeRankings, bool]:
    guild_id = int(actor.guild_id)
    viewer_key = (guild_id, actor.user_id)
    now = monotonic()
    public_cached = _ranking_cache.get(guild_id)
    viewer_cached = _ranking_viewer_cache.get(viewer_key)
    public_is_fresh = (
        public_cached is not None and now - public_cached[1] < RANKING_CACHE_SECONDS
    )
    viewer_is_fresh = (
        viewer_cached is not None and now - viewer_cached[1] < RANKING_CACHE_SECONDS
    )
    if public_is_fresh and viewer_is_fresh:
        assert viewer_cached is not None
        return _without_known_bans(viewer_cached[0], guild_id), False
    lock = _ranking_locks.setdefault(guild_id, asyncio.Lock())
    async with lock:
        now = monotonic()
        public_cached = _ranking_cache.get(guild_id)
        viewer_cached = _ranking_viewer_cache.get(viewer_key)
        public_is_fresh = (
            public_cached is not None and now - public_cached[1] < RANKING_CACHE_SECONDS
        )
        viewer_is_fresh = (
            viewer_cached is not None and now - viewer_cached[1] < RANKING_CACHE_SECONDS
        )
        if public_is_fresh and viewer_is_fresh:
            assert viewer_cached is not None
            return _without_known_bans(viewer_cached[0], guild_id), False
        rankings = await api.rankings(actor)
        if not public_is_fresh:
            _clear_ranking_cache(guild_id)
            _ranking_cache[guild_id] = (rankings, now)
        _ranking_viewer_cache[viewer_key] = (rankings, now)
        return _without_known_bans(rankings, guild_id), not public_is_fresh


async def _publish_configured_ledger(
    interaction: discord.Interaction,
    api: CafeApiClient,
    *,
    record_type: Literal["draw", "redemption"],
    event_id: str,
) -> bool:
    if interaction.guild is None or not isinstance(interaction.client, commands.Bot):
        return False
    try:
        delivered = await publish_pending_for_guild(
            interaction.client, api, interaction.guild
        )
    except CafeApiError:
        logger.exception(
            "Failed to publish Cafe ledger for guild %s", interaction.guild.id
        )
        return False
    return (record_type, event_id) in delivered


def _next_hour_label(now: datetime | None = None) -> str:
    tokyo = ZoneInfo("Asia/Tokyo")
    local_now = now or datetime.now(tokyo)
    next_hour = local_now.astimezone(tokyo).replace(
        minute=0, second=0, microsecond=0
    ) + timedelta(hours=1)
    return next_hour.strftime("%H:%M")


def _normalized_card_search(value: str) -> str:
    return " ".join(value.casefold().split())


async def _send_draw_result(
    interaction: discord.Interaction,
    result: CafeDrawBatch,
    *,
    count: int,
    ledger_published: bool = False,
) -> None:
    if result.status != "drawn":
        if result.status == "confirmation_required":
            message = "無料枠または消費XPが変わったため確定しませんでした。" + (
                "もう一度ボタンを押して内容を確認してください。"
                if count == 1
                else "もう一度まとめ引きの内容を確認してください。"
            )
        elif result.status == "insufficient_xp":
            message = (
                "XPが足りません。現在 "
                f"**{result.wallet_before.available_xp:,} XP** です。"
            )
        elif result.status == "hourly_limit":
            message = (
                f"1時間の上限 **10回** に達しました。"
                f"次は **{_next_hour_label()}** から引けます。"
                if count == 1
                else (
                    f"{count}枚のまとめ引きには、この時間の抽選枠が{count}回分必要です。"
                    f"次は **{_next_hour_label()}** から引けます。"
                )
            )
        else:
            message = "操作IDが別の抽選で使用済みです。もう一度ボタンを押してください。"
        await interaction.followup.send(message, ephemeral=True)
        return
    if len(result.draws) != count:
        await interaction.followup.send(
            (
                "抽選結果を取得できませんでした。"
                if count == 1
                else "まとめ引きの抽選結果を取得できませんでした。"
            ),
            ephemeral=True,
        )
        return
    if not ledger_published:
        await interaction.followup.send(
            (
                "抽選は確定しましたが、カフェ台帳へ投稿できませんでした。"
                "管理者に連絡してください。"
                if count == 1
                else (
                    "まとめ引きは確定しましたが、カフェ台帳へ投稿できませんでした。"
                    "管理者に連絡してください。"
                )
            ),
            ephemeral=True,
        )
        return
    await interaction.followup.send(
        (
            "抽選が完了しました。**カフェ台帳**で結果を確認してください。\n"
            if count == 1
            else (
                f"{count}枚のまとめ引きが完了しました。"
                "**カフェ台帳**で結果を確認してください。\n"
            )
        )
        + f"現在XP: **{result.wallet_after.available_xp:,} XP**",
        ephemeral=True,
    )


async def _send_balance(
    interaction: discord.Interaction,
    *,
    availability: CafeAvailability,
    hourly_limit: int,
) -> None:
    wallet = availability.wallet
    free_status = "利用できます" if availability.has_free_draw else "使用済み"
    await interaction.followup.send(
        (
            f"獲得・受取XP: **{wallet.total_xp:,} XP**\n"
            f"使用・譲渡済み: **{wallet.spent_xp:,} XP**\n"
            f"現在XP: **{wallet.available_xp:,} XP**\n\n"
            f"本日の無料1枚: **{free_status}**\n"
            f"この時間の残り: **{availability.hourly_remaining}/{hourly_limit}回**\n"
            "1日合計の上限はありません。"
        ),
        ephemeral=True,
    )


class DrawConfirmView(discord.ui.View):
    def __init__(
        self,
        *,
        api: CafeApiClient,
        actor: CafeActor,
        requester_id: int,
        display_name: str,
        count: int,
        expected_cost_xp: int,
    ) -> None:
        super().__init__(timeout=120)
        self.api = api
        self.actor = actor
        self.requester_id = requester_id
        self.event_id = str(uuid4())
        self.display_name = display_name
        self.count = count
        self.expected_cost_xp = expected_cost_xp

    @discord.ui.button(label="この内容で引く", style=discord.ButtonStyle.primary)
    async def confirm(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button[DrawConfirmView],
    ) -> None:
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message(
                "本人だけが操作できます。", ephemeral=True
            )
            return
        current_actor = _actor(interaction)
        if (
            current_actor is None
            or current_actor.guild_id != self.actor.guild_id
            or current_actor.user_id != self.actor.user_id
        ):
            await interaction.response.send_message(
                "このサーバーでは利用できません。", ephemeral=True
            )
            return
        if not await _ensure_feature_access(interaction, self.api, current_actor):
            return
        await interaction.response.edit_message(
            content="抽選しています…",
            view=None,
        )
        try:
            result = await self.api.draw(
                current_actor,
                event_id=self.event_id,
                display_name=self.display_name,
                count=self.count,
                expected_cost_xp=self.expected_cost_xp,
            )
        except CafeApiError as exc:
            await _send_api_error(interaction, exc)
            return
        self.stop()
        published = False
        if result.status == "drawn":
            published = await _publish_configured_ledger(
                interaction,
                self.api,
                record_type="draw",
                event_id=self.event_id,
            )
        await _send_draw_result(
            interaction,
            result,
            count=self.count,
            ledger_published=published,
        )

    @discord.ui.button(label="キャンセル", style=discord.ButtonStyle.secondary)
    async def cancel(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button[DrawConfirmView],
    ) -> None:
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message(
                "本人だけが操作できます。", ephemeral=True
            )
            return
        await interaction.response.edit_message(
            content="抽選をキャンセルしました。", view=None
        )
        self.stop()


def _draw_confirmation_text(
    availability: CafeAvailability,
    *,
    capabilities: CafeCapabilities,
    count: int,
    cost_xp: int,
) -> str:
    free_text = "（本日の無料1枚を含む）" if availability.has_free_draw else ""
    draw_label = "1枚を引きます" if count == 1 else f"{count}枚をまとめて引きます"
    minimum_reward = count * capabilities.minimum_draw_reward_xp
    minimum_balance_after = availability.wallet.available_xp + minimum_reward - cost_xp
    reinvest_text = (
        "\n獲得XPを次の1枚の費用に充てながら引きます。"
        if cost_xp > availability.wallet.available_xp
        else ""
    )
    return (
        f"**{draw_label}**{free_text}。\n"
        f"現在XP: **{availability.wallet.available_xp:,} XP**\n"
        f"消費: **{cost_xp:,} XP**\n"
        f"最低獲得: **{minimum_reward:,} XP**\n"
        f"抽選後: **{minimum_balance_after:,} XP以上**\n"
        f"この時間の残り枠: {availability.hourly_remaining} → "
        f"**{availability.hourly_remaining - count}回**"
        f"{reinvest_text}"
    )


async def _draw(
    interaction: discord.Interaction,
    *,
    api: CafeApiClient,
    count: int,
    flexible_maximum: bool = False,
) -> None:
    actor = _actor(interaction)
    if actor is None:
        await interaction.response.send_message(
            "このサーバーでは利用できません。", ephemeral=True
        )
        return
    if not await _ensure_feature_access(interaction, api, actor):
        return
    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        availability = await api.availability(actor, count=count)
        capabilities = await api.capabilities() if flexible_maximum else None
    except CafeApiError as exc:
        await _send_api_error(interaction, exc)
        return
    if availability.hourly_remaining == 0:
        hourly_limit = (
            capabilities.hourly_draw_limit if capabilities is not None else 10
        )
        await interaction.followup.send(
            f"1時間の上限 **{hourly_limit}回** に達しました。"
            f"次は **{_next_hour_label()}** から引けます。",
            ephemeral=True,
        )
        return
    if flexible_maximum and capabilities is not None:
        balance = availability.wallet.available_xp
        affordable_count = 0
        for index in range(min(count, availability.hourly_remaining)):
            cost = (
                0
                if availability.has_free_draw and index == 0
                else capabilities.paid_draw_cost_xp
            )
            if balance < cost:
                break
            balance += capabilities.minimum_draw_reward_xp - cost
            affordable_count += 1
        count = affordable_count
    if count == 0:
        await interaction.followup.send(
            f"XPが足りません。現在 **{availability.wallet.available_xp:,} XP** です。",
            ephemeral=True,
        )
        return
    if count > availability.hourly_remaining:
        await interaction.followup.send(
            f"この時間の残り枠は **{availability.hourly_remaining}回** です。",
            ephemeral=True,
        )
        return
    expected_cost_xp = (
        max(0, count - (1 if availability.has_free_draw else 0))
        * capabilities.paid_draw_cost_xp
        if flexible_maximum and capabilities is not None
        else availability.cost_xp
    )
    if expected_cost_xp == 0:
        try:
            result = await api.draw(
                actor,
                event_id=str(interaction.id),
                display_name=interaction.user.display_name,
                count=count,
                expected_cost_xp=0,
            )
        except CafeApiError as exc:
            await _send_api_error(interaction, exc)
            return
        published = False
        if result.status == "drawn":
            published = await _publish_configured_ledger(
                interaction,
                api,
                record_type="draw",
                event_id=str(interaction.id),
            )
        await _send_draw_result(
            interaction,
            result,
            count=count,
            ledger_published=published,
        )
        return
    if capabilities is None:
        try:
            capabilities = await api.capabilities()
        except CafeApiError as exc:
            await _send_api_error(interaction, exc)
            return
    view = DrawConfirmView(
        api=api,
        actor=actor,
        requester_id=interaction.user.id,
        display_name=interaction.user.display_name,
        count=count,
        expected_cost_xp=expected_cost_xp,
    )
    await interaction.followup.send(
        _draw_confirmation_text(
            availability,
            capabilities=capabilities,
            count=count,
            cost_xp=expected_cost_xp,
        ),
        view=view,
        ephemeral=True,
    )


class CafePanelDrawButton(
    discord.ui.DynamicItem[discord.ui.Button[discord.ui.View]],
    template=r"cafe-collection:draw:(?P<count>1|10):(?P<guild_id>\d+)",
):
    def __init__(self, *, count: int, guild_id: int) -> None:
        self.count = count
        self.guild_id = guild_id
        label = "一枚引く" if count == 1 else "まとめて引く（最大10枚）"
        emoji = "☕" if count == 1 else "🎟️"
        super().__init__(
            discord.ui.Button(
                label=label,
                emoji=emoji,
                style=(
                    discord.ButtonStyle.primary
                    if count == 1
                    else discord.ButtonStyle.success
                ),
                custom_id=f"cafe-collection:draw:{count}:{guild_id}",
                row=0,
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        _interaction: discord.Interaction,
        _item: discord.ui.Item[discord.ui.View],
        match: re.Match[str],
    ) -> CafePanelDrawButton:
        return cls(count=int(match["count"]), guild_id=int(match["guild_id"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id != self.guild_id:
            await interaction.response.send_message(
                "このサーバーでは利用できません。", ephemeral=True
            )
            return
        api = _api(interaction)
        if api is None:
            await interaction.response.send_message(
                "このサーバーでは利用できません。", ephemeral=True
            )
            return
        await _draw(
            interaction,
            api=api,
            count=self.count,
            flexible_maximum=self.count == 10,
        )


class CafePanelCollectionButton(
    discord.ui.DynamicItem[discord.ui.Button[discord.ui.View]],
    template=r"cafe-collection:collection:(?P<guild_id>\d+)",
):
    def __init__(self, *, guild_id: int) -> None:
        self.guild_id = guild_id
        super().__init__(
            discord.ui.Button(
                label="自分の棚・重複交換",
                style=discord.ButtonStyle.secondary,
                custom_id=f"cafe-collection:collection:{guild_id}",
                row=1,
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        _interaction: discord.Interaction,
        _item: discord.ui.Item[discord.ui.View],
        match: re.Match[str],
    ) -> CafePanelCollectionButton:
        return cls(guild_id=int(match["guild_id"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id != self.guild_id:
            await interaction.response.send_message(
                "このサーバーでは利用できません。", ephemeral=True
            )
            return
        api = _api(interaction)
        if api is None:
            await interaction.response.send_message(
                "このサーバーでは利用できません。", ephemeral=True
            )
            return
        try:
            await show_full_collection(interaction, api=api)
        except Exception:
            logger.exception(
                "Failed to show Cafe collection for guild=%s user=%s",
                self.guild_id,
                interaction.user.id,
            )
            if interaction.response.is_done():
                await interaction.followup.send(
                    "カード棚の読み込みに失敗しました。時間をおいてもう一度お試しください。",
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    "カード棚の読み込みに失敗しました。時間をおいてもう一度お試しください。",
                    ephemeral=True,
                )


class CafePanelBalanceButton(
    discord.ui.DynamicItem[discord.ui.Button[discord.ui.View]],
    template=r"cafe-collection:balance:(?P<guild_id>\d+)",
):
    def __init__(self, *, guild_id: int) -> None:
        self.guild_id = guild_id
        super().__init__(
            discord.ui.Button(
                label="自分のXP・残り枠",
                style=discord.ButtonStyle.secondary,
                custom_id=f"cafe-collection:balance:{guild_id}",
                row=1,
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        _interaction: discord.Interaction,
        _item: discord.ui.Item[discord.ui.View],
        match: re.Match[str],
    ) -> CafePanelBalanceButton:
        return cls(guild_id=int(match["guild_id"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id != self.guild_id:
            await interaction.response.send_message(
                "このサーバーでは利用できません。", ephemeral=True
            )
            return
        api = _api(interaction)
        actor = _actor(interaction)
        if api is None or actor is None:
            await interaction.response.send_message(
                "このサーバーでは利用できません。", ephemeral=True
            )
            return
        if not await _ensure_feature_access(interaction, api, actor):
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            availability = await api.availability(actor, count=1)
            capabilities = await api.capabilities()
        except CafeApiError as exc:
            await _send_api_error(interaction, exc)
            return
        await _send_balance(
            interaction,
            availability=availability,
            hourly_limit=capabilities.hourly_draw_limit,
        )


class CafePanelView(discord.ui.View):
    def __init__(self, *, guild_id: int) -> None:
        super().__init__(timeout=None)
        self.add_item(CafePanelDrawButton(count=1, guild_id=guild_id))
        self.add_item(CafePanelDrawButton(count=10, guild_id=guild_id))
        self.add_item(CafePanelCollectionButton(guild_id=guild_id))
        self.add_item(CafePanelBalanceButton(guild_id=guild_id))
        self.add_item(
            discord.ui.Button(
                label="Web図鑑・排出率",
                emoji="📖",
                url=CAFE_COLLECTION_SITE_URL,
                row=1,
            )
        )


class CafeRankingButton(
    discord.ui.DynamicItem[discord.ui.Button[discord.ui.View]],
    template=(
        r"cafe-collection:ranking:"
        r"(?P<category>collection|mastery|sets|rare|treasure|joke|coffee|tea|sweets|culture):"
        r"(?P<guild_id>\d+)"
    ),
):
    def __init__(self, *, category: str, guild_id: int, row: int) -> None:
        self.category = category
        self.guild_id = guild_id
        presentation = CATEGORY_PRESENTATIONS[category]
        super().__init__(
            discord.ui.Button(
                label=presentation.button_label,
                emoji=presentation.emoji,
                style=(
                    discord.ButtonStyle.primary
                    if category == "collection"
                    else discord.ButtonStyle.secondary
                ),
                custom_id=f"cafe-collection:ranking:{category}:{guild_id}",
                row=row,
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        _interaction: discord.Interaction,
        item: discord.ui.Item[discord.ui.View],
        match: re.Match[str],
    ) -> CafeRankingButton:
        return cls(
            category=match["category"],
            guild_id=int(match["guild_id"]),
            row=item.row or 0,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id != self.guild_id:
            await interaction.response.send_message(
                "このサーバーでは利用できません。", ephemeral=True
            )
            return
        actor = _actor(interaction)
        api = _api(interaction)
        if actor is None or api is None:
            await interaction.response.send_message(
                "このサーバーでは利用できません。", ephemeral=True
            )
            return
        if not await _ensure_feature_access(interaction, api, actor):
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            rankings, refreshed = await _get_cached_rankings(api, actor)
        except CafeApiError as exc:
            await _send_api_error(interaction, exc)
            return
        if refreshed and interaction.message is not None:
            try:
                await interaction.message.edit(
                    embed=build_ranking_panel_embed(rankings),
                    view=CafeRankingView(guild_id=self.guild_id),
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            except discord.HTTPException:
                logger.exception(
                    "Failed to refresh Cafe ranking panel for guild %s",
                    self.guild_id,
                )
        await interaction.followup.send(
            embed=build_ranking_detail_embed(
                rankings,
                category_key=self.category,
                viewer_id=str(interaction.user.id),
            ),
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )


class CafeRankingView(discord.ui.View):
    def __init__(self, *, guild_id: int) -> None:
        super().__init__(timeout=None)
        for index, category in enumerate(CATEGORY_PRESENTATIONS):
            self.add_item(
                CafeRankingButton(
                    category=category,
                    guild_id=guild_id,
                    row=index // 5,
                )
            )
        self.add_item(
            discord.ui.Button(
                label="全ランキングをWebで見る",
                emoji="🌐",
                url=CAFE_RANKINGS_SITE_URL,
                row=2,
            )
        )


def register_dynamic_items(bot: commands.Bot) -> None:
    bot.add_dynamic_items(
        CafePanelDrawButton,
        CafePanelCollectionButton,
        CafePanelBalanceButton,
        CafeRankingButton,
    )


async def _find_existing_message(
    channel: discord.TextChannel,
    *,
    bot_user_id: int,
    stored_channel_id: str | None,
    stored_message_id: str | None,
    title: str,
) -> discord.Message | None:
    if stored_channel_id == str(channel.id) and stored_message_id is not None:
        try:
            message = await channel.fetch_message(int(stored_message_id))
        except discord.NotFound:
            pass
        else:
            if message.author.id == bot_user_id:
                return message
    async for message in channel.history(limit=None):
        if (
            message.author.id == bot_user_id
            and message.embeds
            and message.embeds[0].title == title
        ):
            return message
    return None


async def _find_or_create_channel(
    guild: discord.Guild,
    name: str,
    configured_id: str | None,
) -> discord.TextChannel:
    configured = (
        guild.get_channel(int(configured_id)) if configured_id is not None else None
    )
    existing = configured if isinstance(configured, discord.TextChannel) else None
    if existing is None and configured_id is None:
        existing = discord.utils.get(guild.text_channels, name=name)
    me = guild.me
    overwrites: dict[
        discord.Role | discord.Member | discord.Object,
        discord.PermissionOverwrite,
    ] = {
        guild.default_role: discord.PermissionOverwrite(
            view_channel=True,
            read_message_history=True,
            send_messages=False,
        )
    }
    if me is not None:
        overwrites[me] = discord.PermissionOverwrite(
            view_channel=True,
            read_message_history=True,
            send_messages=True,
            embed_links=True,
            attach_files=True,
        )
    channel = (
        existing
        if existing is not None
        else await guild.create_text_channel(name, overwrites=overwrites)
    )
    default_permissions = channel.overwrites_for(guild.default_role)
    default_permissions.update(
        view_channel=True,
        read_message_history=True,
        send_messages=False,
    )
    await channel.set_permissions(guild.default_role, overwrite=default_permissions)
    if me is not None:
        bot_permissions = channel.overwrites_for(me)
        bot_permissions.update(
            view_channel=True,
            read_message_history=True,
            send_messages=True,
            embed_links=True,
            attach_files=True,
        )
        await channel.set_permissions(me, overwrite=bot_permissions)
    return channel


class CafeCog(commands.Cog):
    cafe_collection_group = app_commands.Group(
        name="cafe-collection",
        description="カフェ・コレクションの管理",
        guild_only=True,
    )
    access_role = app_commands.Group(
        name="access-role",
        description="カフェ・コレクションの利用ロール管理",
        parent=cafe_collection_group,
    )

    def __init__(self, bot: commands.Bot, api: CafeApiClient) -> None:
        self.bot = bot
        self.api = api
        self._ready_repaired = False
        self._ranking_refresh_lock = asyncio.Lock()

    async def cog_load(self) -> None:
        self.ranking_refresh_loop.start()

    async def cog_unload(self) -> None:
        self.ranking_refresh_loop.cancel()

    async def _refresh_configured_ranking(self, guild: discord.Guild) -> None:
        if self.bot.user is None:
            return
        async with self._ranking_refresh_lock:
            actor = CafeActor(
                guild_id=str(guild.id),
                user_id=str(self.bot.user.id),
                role_ids=[],
                can_manage_guild=True,
            )
            layout = await self.api.layout(actor)
            ranking_channel = (
                guild.get_channel(int(layout.ranking_channel_id))
                if layout.ranking_channel_id is not None
                else None
            )
            if isinstance(ranking_channel, discord.TextChannel):
                await self._upsert_ranking(
                    actor=actor,
                    guild=guild,
                    channel=ranking_channel,
                )

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User) -> None:
        _ranking_banned_user_ids.setdefault(guild.id, set()).add(str(user.id))
        _clear_ranking_cache(guild.id)
        try:
            await self._refresh_configured_ranking(guild)
        except (CafeApiError, discord.HTTPException, OSError):
            logger.exception("Failed to refresh Cafe ranking after a ban")

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User) -> None:
        _ranking_banned_user_ids.setdefault(guild.id, set()).discard(str(user.id))
        _clear_ranking_cache(guild.id)
        try:
            await self._refresh_configured_ranking(guild)
        except (CafeApiError, discord.HTTPException, OSError):
            logger.exception("Failed to refresh Cafe ranking after an unban")

    @tasks.loop(minutes=1)
    async def ranking_refresh_loop(self) -> None:
        for guild in self.bot.guilds:
            _clear_ranking_cache(guild.id)
            try:
                await self._refresh_configured_ranking(guild)
            except (CafeApiError, discord.HTTPException, OSError):
                logger.exception(
                    "Failed to refresh configured Cafe ranking for guild %s",
                    guild.id,
                )

    @ranking_refresh_loop.before_loop
    async def before_ranking_refresh_loop(self) -> None:
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        if self._ready_repaired or self.bot.user is None:
            return
        self._ready_repaired = True
        for guild in self.bot.guilds:
            actor = CafeActor(
                guild_id=str(guild.id),
                user_id=str(self.bot.user.id),
                role_ids=[],
                can_manage_guild=True,
            )
            try:
                await self._ensure_setup(
                    actor=actor,
                    guild=guild,
                    require_existing=True,
                )
                await self._refresh_configured_ranking(guild)
                await publish_pending_for_guild(self.bot, self.api, guild)
            except (CafeApiError, discord.HTTPException, OSError):
                logger.exception("Failed to repair Cafe setup for guild %s", guild.id)

    async def _delete_legacy_ledger_header(
        self,
        *,
        channel: discord.TextChannel,
        message_id: str | None,
    ) -> None:
        if self.bot.user is None:
            return
        if message_id is not None:
            with contextlib.suppress(discord.NotFound, discord.Forbidden):
                message = await channel.fetch_message(int(message_id))
                if (
                    message.author.id == self.bot.user.id
                    and message.embeds
                    and message.embeds[0].title == LEDGER_TITLE
                ):
                    await message.delete()
                    return
        async for message in channel.history(limit=100):
            if (
                message.author.id == self.bot.user.id
                and message.embeds
                and message.embeds[0].title == LEDGER_TITLE
            ):
                await message.delete()

    async def _upsert_panel(
        self,
        *,
        guild: discord.Guild,
        channel: discord.TextChannel,
        stored_channel_id: str | None,
        stored_message_id: str | None,
    ) -> discord.Message:
        if self.bot.user is None:
            raise CafeApiError("Botユーザーを取得できません")
        message = await _find_existing_message(
            channel,
            bot_user_id=self.bot.user.id,
            stored_channel_id=stored_channel_id,
            stored_message_id=stored_message_id,
            title=PANEL_TITLE,
        )
        panel_file = discord.File(
            ASSET_DIR / "panel-cabinet.jpg",
            filename="panel-cabinet.jpg",
        )
        try:
            if message is None:
                return await channel.send(
                    embed=build_panel_embed(await self.api.capabilities()),
                    file=panel_file,
                    view=CafePanelView(guild_id=guild.id),
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            return await message.edit(
                content=None,
                embed=build_panel_embed(await self.api.capabilities()),
                attachments=[panel_file],
                suppress=False,
                view=CafePanelView(guild_id=guild.id),
                allowed_mentions=discord.AllowedMentions.none(),
            )
        finally:
            panel_file.close()

    async def _ensure_setup(
        self,
        *,
        actor: CafeActor,
        guild: discord.Guild,
        require_existing: bool,
    ) -> tuple[discord.TextChannel, discord.TextChannel] | None:
        lock = _setup_locks.setdefault(guild.id, asyncio.Lock())
        async with lock:
            layout = await self.api.layout(actor)
            if layout.panel_channel_id is None and require_existing:
                ledger = (
                    guild.get_channel(int(layout.ledger_channel_id))
                    if layout.ledger_channel_id is not None
                    else None
                )
                if isinstance(ledger, discord.TextChannel):
                    await self._delete_legacy_ledger_header(
                        channel=ledger,
                        message_id=layout.ledger_message_id,
                    )
                    await self.api.save_placement(
                        actor,
                        placement="ledger",
                        channel_id=str(ledger.id),
                        message_id=None,
                    )
                return None
            counter = await _find_or_create_channel(
                guild,
                COUNTER_NAME,
                layout.panel_channel_id,
            )
            ledger = await _find_or_create_channel(
                guild,
                LEDGER_NAME,
                layout.ledger_channel_id,
            )
            await self._delete_legacy_ledger_header(
                channel=ledger,
                message_id=layout.ledger_message_id,
            )
            panel = await self._upsert_panel(
                guild=guild,
                channel=counter,
                stored_channel_id=layout.panel_channel_id,
                stored_message_id=layout.panel_message_id,
            )
            await self.api.save_placement(
                actor,
                placement="panel",
                channel_id=str(counter.id),
                message_id=str(panel.id),
            )
            await self.api.save_placement(
                actor,
                placement="ledger",
                channel_id=str(ledger.id),
                message_id=None,
            )
            return counter, ledger

    async def _upsert_ranking(
        self,
        *,
        actor: CafeActor,
        guild: discord.Guild,
        channel: discord.TextChannel,
    ) -> discord.Message | None:
        layout = await self.api.layout(actor)
        if layout.panel_channel_id is None:
            return None
        if self.bot.user is None:
            raise CafeApiError("Botユーザーを取得できません")
        message = await _find_existing_message(
            channel,
            bot_user_id=self.bot.user.id,
            stored_channel_id=layout.ranking_channel_id,
            stored_message_id=layout.ranking_message_id,
            title=RANKING_TITLE,
        )
        rankings, _ = await _get_cached_rankings(self.api, actor)
        embed = build_ranking_panel_embed(rankings)
        view = CafeRankingView(guild_id=guild.id)
        if message is None:
            message = await channel.send(
                embed=embed,
                view=view,
                allowed_mentions=discord.AllowedMentions.none(),
            )
        else:
            message = await message.edit(
                content=None,
                embed=embed,
                view=view,
                suppress=False,
                allowed_mentions=discord.AllowedMentions.none(),
            )
        await self.api.save_placement(
            actor,
            placement="ranking",
            channel_id=str(channel.id),
            message_id=str(message.id),
        )
        return message

    async def protection_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        actor = _actor(interaction)
        if actor is None:
            return []
        try:
            collection = await self.api.collection_preview(actor)
        except CafeApiError:
            return []
        query = _normalized_card_search(current)
        ranked: list[tuple[int, int, CafeCollectionCard]] = []
        for index, card in enumerate(collection.cards):
            if card.count <= 0:
                continue
            name = _normalized_card_search(card.name)
            key = _normalized_card_search(card.key)
            rarity = _normalized_card_search(
                RARITY_LABELS.get(card.rarity, card.rarity)
            )
            if not query:
                rank = 0 if card.is_protected else 1
            elif query in {name, key}:
                rank = 0
            elif name.startswith(query):
                rank = 1
            elif query in name:
                rank = 2
            elif key.startswith(query):
                rank = 3
            elif query in key or query in rarity:
                rank = 4
            else:
                continue
            ranked.append((rank, index, card))
        ranked.sort(key=lambda item: (item[0], item[1]))
        return [
            app_commands.Choice(
                name=(
                    f"{'解除' if card.is_protected else '保護'}｜"
                    f"{RARITY_LABELS.get(card.rarity, card.rarity)}｜{card.name}"
                )[:100],
                value=card.key,
            )
            for _, _, card in ranked[:25]
        ]

    async def _access_role(
        self,
        interaction: discord.Interaction,
        *,
        action: Literal["add", "remove", "list"],
        role: discord.Role | None = None,
    ) -> None:
        actor = _actor(interaction)
        if actor is None:
            await interaction.response.send_message(
                "サーバー内で実行してください。", ephemeral=True
            )
            return
        try:
            if action == "add" and role is not None:
                result = await self.api.add_access_role(actor, role_id=str(role.id))
            elif action == "remove" and role is not None:
                result = await self.api.remove_access_role(actor, role_id=str(role.id))
            else:
                result = await self.api.access_roles(actor)
        except CafeApiError as exc:
            await _send_api_error(interaction, exc)
            return
        if action == "list":
            visible = result.role_ids[:20]
            formatted = "、".join(f"<@&{role_id}>" for role_id in visible)
            if len(result.role_ids) > len(visible):
                formatted += f"、ほか {len(result.role_ids) - len(visible)}件"
            message = (
                "カフェ・コレクションの利用ロール: " + formatted
                if result.role_ids
                else "利用ロールは未設定です。現在は全員が利用できます。"
            )
        elif action == "add" and role is not None:
            message = (
                f"カフェ・コレクションの利用ロールに {role.mention} を追加しました。"
                if result.changed
                else f"{role.mention} はすでに利用ロールへ追加されています。"
            )
        elif role is not None:
            message = (
                f"カフェ・コレクションの利用ロールから {role.mention} を削除しました。"
                if result.changed
                else f"{role.mention} は利用ロールに設定されていません。"
            )
        else:  # pragma: no cover - command wiring always provides a role
            message = "ロールを指定してください。"
        await interaction.response.send_message(
            message,
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @access_role.command(name="add", description="利用できるロールを追加")
    @app_commands.describe(role="カフェ・コレクションの利用を許可するロール")
    @app_commands.checks.has_permissions(administrator=True)
    async def access_add(
        self, interaction: discord.Interaction, role: discord.Role
    ) -> None:
        await self._access_role(interaction, action="add", role=role)

    @access_role.command(name="remove", description="利用ロールを削除")
    @app_commands.describe(role="カフェ・コレクションの利用許可から外すロール")
    @app_commands.checks.has_permissions(administrator=True)
    async def access_remove(
        self, interaction: discord.Interaction, role: discord.Role
    ) -> None:
        await self._access_role(interaction, action="remove", role=role)

    @access_role.command(name="list", description="利用ロールを表示")
    @app_commands.checks.has_permissions(administrator=True)
    async def access_list(self, interaction: discord.Interaction) -> None:
        await self._access_role(interaction, action="list")

    @cafe_collection_group.command(
        name="setup",
        description="カウンター・台帳・抽選パネルを作成または修復",
    )
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.checks.bot_has_permissions(manage_channels=True)
    async def setup_gacha(self, interaction: discord.Interaction) -> None:
        actor = _actor(interaction)
        if actor is None or interaction.guild is None:
            await interaction.response.send_message(
                "サーバー内で実行してください。", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            channels = await self._ensure_setup(
                actor=actor,
                guild=interaction.guild,
                require_existing=False,
            )
        except (CafeApiError, discord.HTTPException, OSError):
            logger.exception("Failed to set up Cafe for guild %s", interaction.guild.id)
            channels = None
        if channels is None:
            await interaction.followup.send(
                "セットアップできませんでした。", ephemeral=True
            )
            return
        counter, ledger = channels
        await publish_pending_for_guild(self.bot, self.api, interaction.guild)
        await interaction.followup.send(
            f"セットアップしました: {counter.mention} / {ledger.mention}",
            ephemeral=True,
        )

    @cafe_collection_group.command(
        name="leaderboard-panel",
        description="選んだチャンネルへランキングパネルを投稿または更新",
    )
    @app_commands.describe(channel="ランキングパネルの投稿先")
    @app_commands.checks.has_permissions(administrator=True)
    async def leaderboard_panel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ) -> None:
        guild = interaction.guild
        actor = _actor(interaction)
        if guild is None or actor is None or channel.guild.id != guild.id:
            await interaction.response.send_message(
                "このサーバーのテキストチャンネルを選んでください。",
                ephemeral=True,
            )
            return
        me = guild.me
        if me is None:
            await interaction.response.send_message(
                "Botのサーバー情報を取得できませんでした。", ephemeral=True
            )
            return
        permissions = channel.permissions_for(me)
        if not (
            permissions.view_channel
            and permissions.read_message_history
            and permissions.send_messages
            and permissions.embed_links
        ):
            await interaction.response.send_message(
                "選んだチャンネルで、閲覧・履歴閲覧・送信・埋め込みの権限が必要です。",
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            panel = await self._upsert_ranking(
                actor=actor,
                guild=guild,
                channel=channel,
            )
        except (CafeApiError, discord.HTTPException):
            logger.exception(
                "Failed to publish Cafe leaderboard for guild %s", guild.id
            )
            panel = None
        if panel is None:
            await interaction.followup.send(
                "先に `/cafe-collection setup` を実行してください。",
                ephemeral=True,
            )
            return
        await interaction.followup.send(
            f"ランキングパネルを {channel.mention} に投稿・更新しました。",
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @cafe_collection_group.command(
        name="stats", description="利用状況とXP収支を管理者だけに表示"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def stats(self, interaction: discord.Interaction) -> None:
        actor = _actor(interaction)
        if actor is None:
            await interaction.response.send_message(
                "サーバー内で実行してください。", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            analytics = await self.api.analytics(actor)
            capabilities = await self.api.capabilities()
        except CafeApiError as exc:
            await _send_api_error(interaction, exc)
            return
        await interaction.followup.send(
            embed=build_analytics_embed(
                analytics,
                catalog_size=capabilities.catalog_size,
            ),
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @cafe_collection_group.command(
        name="protect",
        description="名前検索で所持カードの保護／解除を切り替える",
    )
    @app_commands.describe(card="カード名を入力すると所持カードが候補表示されます")
    @app_commands.autocomplete(card=protection_autocomplete)
    async def protect(self, interaction: discord.Interaction, card: str) -> None:
        actor = _actor(interaction)
        if actor is None:
            await interaction.response.send_message(
                "サーバー内で実行してください。", ephemeral=True
            )
            return
        if not await _ensure_feature_access(interaction, self.api, actor):
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            collection = await self.api.collection(actor)
            normalized = _normalized_card_search(card)
            matches = [
                item
                for item in collection.cards
                if item.count > 0
                and (
                    item.key == card or _normalized_card_search(item.name) == normalized
                )
            ]
            selected = matches[0] if len(matches) == 1 else None
            if selected is None:
                await interaction.followup.send(
                    "そのカードは現在所持していません。カード欄の候補から選び直してください。",
                    ephemeral=True,
                )
                return
            result = await self.api.set_protection(
                actor,
                reward_key=selected.key,
                protected=not selected.is_protected,
            )
        except CafeApiError as exc:
            await _send_api_error(interaction, exc)
            return
        if result.status != "updated":
            await interaction.followup.send(
                "所持状態が変わったため設定できませんでした。もう一度お試しください。",
                ephemeral=True,
            )
            return
        await interaction.followup.send(
            (
                f"🔒 **{result.reward_name}** を保護しました。"
                "今後のXP・メダル交換から除外します。"
                if result.protected
                else f"🔓 **{result.reward_name}** の保護を解除しました。"
            ),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    api = getattr(bot, "cafe_api", None)
    if not isinstance(api, CafeApiClient):
        raise RuntimeError("CafeApiClient is not configured")
    register_dynamic_items(bot)
    await bot.add_cog(CafeCog(bot, api))
