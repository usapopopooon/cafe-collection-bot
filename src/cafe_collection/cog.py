"""Discord commands backed by level-bot's transactional Cafe API."""

from __future__ import annotations

import asyncio
import logging
import re
from io import BytesIO
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from cafe_collection.assets import ASSET_DIR, card_image_path
from cafe_collection.collection_image import RARITY_LABELS, render_collection_pages
from cafe_collection.collection_ui import show_full_collection
from cafe_collection.discord_context import (
    actor_from_interaction as _actor,
)
from cafe_collection.discord_context import (
    api_from_interaction as _api,
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
    CafeLayout,
)
from cafe_collection.presentation import (
    CAFE_COLLECTION_SITE_URL,
    CAFE_RANKINGS_SITE_URL,
    CATEGORY_PRESENTATIONS,
    LEDGER_TITLE,
    PANEL_TITLE,
    RANKING_TITLE,
    build_analytics_embed,
    build_ledger_embed,
    build_panel_embed,
    build_ranking_detail_embed,
    build_ranking_panel_embed,
)

RARITY_CHOICES = [
    app_commands.Choice(name="N", value="C"),
    app_commands.Choice(name="HN", value="UC"),
    app_commands.Choice(name="R", value="R"),
    app_commands.Choice(name="SR", value="SR"),
    app_commands.Choice(name="SSR", value="SSR"),
    app_commands.Choice(name="UR", value="UR"),
    app_commands.Choice(name="幻", value="MYTHIC"),
]

Placement = Literal["panel", "ledger", "ranking"]
logger = logging.getLogger(__name__)


async def _publish_configured_ledger(
    interaction: discord.Interaction, api: CafeApiClient
) -> None:
    if interaction.guild is None or not isinstance(interaction.client, commands.Bot):
        return
    try:
        await publish_pending_for_guild(interaction.client, api, interaction.guild)
    except CafeApiError:
        logger.exception(
            "Failed to publish Cafe ledger for guild %s", interaction.guild.id
        )


async def _send_draw_result(
    interaction: discord.Interaction,
    result: CafeDrawBatch,
) -> None:
    if result.status != "drawn":
        messages = {
            "confirmation_required": (
                "無料枠または消費XPが変わりました。もう一度お試しください。"
            ),
            "insufficient_xp": "XPが足りません。",
            "hourly_limit": "1時間の抽選上限に達しています。",
            "conflict": "操作IDが別の抽選で使用済みです。もう一度お試しください。",
        }
        await interaction.followup.send(messages[result.status], ephemeral=True)
        return
    files: list[discord.File] = []
    embeds: list[discord.Embed] = []
    try:
        for draw in result.draws:
            image_path = card_image_path(draw.reward_key)
            if image_path is None or image_path.name != draw.image_filename:
                await interaction.followup.send(
                    "画像バージョンが抽選結果と一致しません。管理者に連絡してください。",
                    ephemeral=True,
                )
                return
            filename = f"{draw.batch_position:02d}-{draw.image_filename}"
            files.append(discord.File(image_path, filename=filename))
            embed = discord.Embed(
                title=(
                    f"☕ {RARITY_LABELS.get(draw.rarity, draw.rarity)}｜"
                    f"{draw.reward_name}"
                ),
                description=draw.reward_description,
                color=discord.Color.from_rgb(139, 90, 60),
            )
            embed.add_field(
                name="結果",
                value=(
                    f"{'NEW' if not draw.was_duplicate else '重複'} / "
                    f"所持 {draw.owned_count}枚 / +{draw.reward_xp:,} XP"
                ),
                inline=False,
            )
            embed.set_image(url=f"attachment://{filename}")
            embeds.append(embed)
        await interaction.followup.send(
            content=(
                f"現在XP: **{result.wallet_after.available_xp:,} XP**\n"
                "結果は指定されたカフェ台帳にも順次反映されます。"
            ),
            embeds=embeds,
            files=files,
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )
    finally:
        for file in files:
            file.close()


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
        allowed_mentions=discord.AllowedMentions.none(),
    )


class DrawConfirmView(discord.ui.View):
    def __init__(
        self,
        *,
        api: CafeApiClient,
        actor: CafeActor,
        requester_id: int,
        event_id: str,
        display_name: str,
        count: int,
        expected_cost_xp: int,
    ) -> None:
        super().__init__(timeout=120)
        self.api = api
        self.actor = actor
        self.requester_id = requester_id
        self.event_id = event_id
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
                "この確認は抽選を開始した本人専用です。", ephemeral=True
            )
            return
        current_actor = _actor(interaction)
        if (
            current_actor is None
            or current_actor.guild_id != self.actor.guild_id
            or current_actor.user_id != self.actor.user_id
        ):
            await interaction.response.send_message(
                "このサーバーでは確定できません。", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
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
        await _send_draw_result(interaction, result)
        if result.status == "drawn":
            await _publish_configured_ledger(interaction, self.api)


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
            "サーバー内でのみ利用できます。", ephemeral=True
        )
        return
    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        availability = await api.availability(actor, count=count)
        capabilities = await api.capabilities() if flexible_maximum else None
    except CafeApiError as exc:
        await _send_api_error(interaction, exc)
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
    event_id = f"cafe-bot:{interaction.id}"
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
                event_id=event_id,
                display_name=interaction.user.display_name,
                count=count,
                expected_cost_xp=0,
            )
        except CafeApiError as exc:
            await _send_api_error(interaction, exc)
            return
        await _send_draw_result(interaction, result)
        if result.status == "drawn":
            await _publish_configured_ledger(interaction, api)
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
        event_id=event_id,
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
        allowed_mentions=discord.AllowedMentions.none(),
    )


async def _collection(
    interaction: discord.Interaction,
    *,
    api: CafeApiClient,
    rarity_value: str,
    rarity_name: str,
) -> None:
    actor = _actor(interaction)
    if actor is None:
        await interaction.response.send_message(
            "サーバー内でのみ利用できます。", ephemeral=True
        )
        return
    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        collection = await api.collection(actor)
    except CafeApiError as exc:
        await _send_api_error(interaction, exc)
        return
    cards = [card for card in collection.cards if card.rarity == rarity_value]
    try:
        pages = await asyncio.to_thread(render_collection_pages, cards)
    except ValueError:
        await interaction.followup.send(
            "画像バージョンがコレクションと一致しません。管理者に連絡してください。",
            ephemeral=True,
        )
        return
    files: list[discord.File] = []
    embeds: list[discord.Embed] = []
    try:
        for page_number, image in enumerate(pages, start=1):
            filename = f"collection-{rarity_value.lower()}-{page_number}.jpg"
            files.append(discord.File(BytesIO(image), filename=filename))
            embed = discord.Embed(
                title=f"☕ カフェカード棚｜{rarity_name}",
                description=(
                    f"収集 {sum(card.count > 0 for card in cards)}/{len(cards)}種"
                    f"（{page_number}/{len(pages)}ページ）"
                ),
                color=discord.Color.from_rgb(139, 90, 60),
            )
            embed.set_image(url=f"attachment://{filename}")
            embeds.append(embed)
        await interaction.followup.send(
            embeds=embeds,
            files=files,
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )
    finally:
        for file in files:
            file.close()


class CafePanelDrawButton(
    discord.ui.DynamicItem[discord.ui.Button[discord.ui.View]],
    template=r"cafe-collection:draw:(?P<count>1|10):(?P<guild_id>\d+)",
):
    def __init__(self, *, count: int, guild_id: int) -> None:
        self.count = count
        self.guild_id = guild_id
        label = "1枚引く" if count == 1 else "まとめて引く（最大10枚）"
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
                "このサーバーのパネルではありません。", ephemeral=True
            )
            return
        api = _api(interaction)
        if api is None:
            await interaction.response.send_message(
                "カフェのデータサービスが設定されていません。", ephemeral=True
            )
            return
        await _draw(
            interaction,
            api=api,
            count=self.count,
            flexible_maximum=self.count == 10,
        )


class CafeRaritySelect(discord.ui.Select[discord.ui.View]):
    def __init__(self, *, requester_id: int, guild_id: int) -> None:
        self.requester_id = requester_id
        self.guild_id = guild_id
        super().__init__(
            placeholder="表示するレアリティを選択",
            options=[
                discord.SelectOption(label=choice.name, value=choice.value)
                for choice in RARITY_CHOICES
            ],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message(
                "この選択メニューは開いた本人専用です。", ephemeral=True
            )
            return
        if interaction.guild_id != self.guild_id:
            await interaction.response.send_message(
                "このサーバーでは表示できません。", ephemeral=True
            )
            return
        api = _api(interaction)
        if api is None:
            await interaction.response.send_message(
                "カフェのデータサービスが設定されていません。", ephemeral=True
            )
            return
        rarity_value = self.values[0]
        rarity_name = next(
            choice.name for choice in RARITY_CHOICES if choice.value == rarity_value
        )
        await _collection(
            interaction,
            api=api,
            rarity_value=rarity_value,
            rarity_name=rarity_name,
        )


class CafeRaritySelectView(discord.ui.View):
    def __init__(self, *, requester_id: int, guild_id: int) -> None:
        super().__init__(timeout=120)
        self.add_item(CafeRaritySelect(requester_id=requester_id, guild_id=guild_id))


class CafePanelCollectionButton(
    discord.ui.DynamicItem[discord.ui.Button[discord.ui.View]],
    template=r"cafe-collection:collection:(?P<guild_id>\d+)",
):
    def __init__(self, *, guild_id: int) -> None:
        self.guild_id = guild_id
        super().__init__(
            discord.ui.Button(
                label="自分の棚・重複交換",
                emoji="🗃️",
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
                "このサーバーのパネルではありません。", ephemeral=True
            )
            return
        api = _api(interaction)
        if api is None:
            await interaction.response.send_message(
                "カフェのデータサービスが設定されていません。", ephemeral=True
            )
            return
        await show_full_collection(interaction, api=api)


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
                "このサーバーのパネルではありません。", ephemeral=True
            )
            return
        api = _api(interaction)
        actor = _actor(interaction)
        if api is None or actor is None:
            await interaction.response.send_message(
                "カフェのデータサービスを利用できません。", ephemeral=True
            )
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
                label="カフェ図鑑",
                emoji="🌐",
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
                label=presentation.label,
                emoji=presentation.emoji,
                style=discord.ButtonStyle.secondary,
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
                "このサーバーのランキングではありません。", ephemeral=True
            )
            return
        actor = _actor(interaction)
        api = _api(interaction)
        if actor is None or api is None:
            await interaction.response.send_message(
                "ランキングを取得できません。", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            rankings = await api.rankings(actor)
        except CafeApiError as exc:
            await _send_api_error(interaction, exc)
            return
        if interaction.message is not None:
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
                label="Webランキング",
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


def _placement_ids(
    layout: CafeLayout,
    placement: Placement,
) -> tuple[str | None, str | None]:
    return (
        getattr(layout, f"{placement}_channel_id"),
        getattr(layout, f"{placement}_message_id"),
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
    async for message in channel.history(limit=100):
        if (
            message.author.id == bot_user_id
            and message.embeds
            and message.embeds[0].title == title
        ):
            return message
    return None


def _can_publish(
    channel: discord.TextChannel,
    *,
    require_attachment: bool,
) -> bool:
    member = channel.guild.me
    if member is None:
        return False
    permissions = channel.permissions_for(member)
    return (
        permissions.view_channel
        and permissions.send_messages
        and permissions.embed_links
        and permissions.read_message_history
        and (permissions.attach_files or not require_attachment)
    )


class CafeCog(
    commands.GroupCog, group_name="cafe", group_description="カフェ・コレクション"
):
    access_role = app_commands.Group(
        name="access-role",
        description="カフェ・コレクションの利用ロールを管理",
    )

    def __init__(self, api: CafeApiClient) -> None:
        self.api = api

    async def _publish(
        self,
        interaction: discord.Interaction,
        *,
        channel: discord.TextChannel | None,
        placement: Placement,
    ) -> None:
        actor = _actor(interaction)
        target = channel or (
            interaction.channel
            if isinstance(interaction.channel, discord.TextChannel)
            else None
        )
        if actor is None or interaction.guild is None or target is None:
            await interaction.response.send_message(
                "サーバーのテキストチャンネルで実行してください。", ephemeral=True
            )
            return
        if not actor.can_manage_guild:
            await interaction.response.send_message(
                "サーバー管理権限が必要です。", ephemeral=True
            )
            return
        if target.guild.id != interaction.guild.id:
            await interaction.response.send_message(
                "このサーバーのチャンネルを指定してください。", ephemeral=True
            )
            return
        require_attachment = placement == "panel"
        if not _can_publish(target, require_attachment=require_attachment):
            await interaction.response.send_message(
                "指定先でメッセージ・埋め込み・履歴を扱う権限が足りません。",
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            layout = await self.api.layout(actor)
            if placement == "panel":
                embed = build_panel_embed(await self.api.capabilities())
                view: discord.ui.View = CafePanelView(guild_id=interaction.guild.id)
                title = PANEL_TITLE
            elif placement == "ledger":
                embed = build_ledger_embed()
                view = discord.ui.View(timeout=None)
                title = LEDGER_TITLE
            else:
                embed = build_ranking_panel_embed(await self.api.rankings(actor))
                view = CafeRankingView(guild_id=interaction.guild.id)
                title = RANKING_TITLE
            stored_channel_id, stored_message_id = _placement_ids(layout, placement)
            bot_user = interaction.client.user
            if bot_user is None:
                raise CafeApiError("Botユーザーを取得できません")
            message = await _find_existing_message(
                target,
                bot_user_id=bot_user.id,
                stored_channel_id=stored_channel_id,
                stored_message_id=stored_message_id,
                title=title,
            )
            if placement == "panel":
                panel_file = discord.File(
                    ASSET_DIR / "panel-cabinet.jpg",
                    filename="panel-cabinet.jpg",
                )
                try:
                    if message is None:
                        message = await target.send(
                            embed=embed,
                            file=panel_file,
                            view=view,
                            allowed_mentions=discord.AllowedMentions.none(),
                        )
                    else:
                        message = await message.edit(
                            embed=embed,
                            attachments=[panel_file],
                            view=view,
                            allowed_mentions=discord.AllowedMentions.none(),
                        )
                finally:
                    panel_file.close()
            elif message is None:
                message = await target.send(
                    embed=embed,
                    view=view,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            else:
                message = await message.edit(
                    embed=embed,
                    view=view,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            await self.api.save_placement(
                actor,
                placement=placement,
                channel_id=str(target.id),
                message_id=str(message.id),
            )
        except CafeApiError as exc:
            await _send_api_error(interaction, exc)
            return
        except discord.HTTPException:
            await interaction.followup.send(
                "Discordへの投稿または更新に失敗しました。権限を確認してください。",
                ephemeral=True,
            )
            return
        labels = {"panel": "パネル", "ledger": "台帳", "ranking": "ランキング"}
        await interaction.followup.send(
            f"{target.mention} に{labels[placement]}を設定しました。",
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @app_commands.command(name="draw", description="カフェカードを1〜10枚引きます")
    @app_commands.describe(count="引く枚数（1〜10枚）")
    async def draw(
        self,
        interaction: discord.Interaction,
        count: app_commands.Range[int, 1, 10] = 1,
    ) -> None:
        await _draw(interaction, api=self.api, count=count)

    @app_commands.command(
        name="collection", description="レアリティ別のカード棚を表示します"
    )
    @app_commands.choices(rarity=RARITY_CHOICES)
    async def collection(
        self,
        interaction: discord.Interaction,
        rarity: app_commands.Choice[str] | None = None,
    ) -> None:
        if rarity is None:
            await show_full_collection(interaction, api=self.api)
            return
        await _collection(
            interaction,
            api=self.api,
            rarity_value=rarity.value,
            rarity_name=rarity.name,
        )

    @app_commands.command(name="balance", description="自分のXPと抽選の残り枠を表示")
    async def balance(self, interaction: discord.Interaction) -> None:
        actor = _actor(interaction)
        if actor is None:
            await interaction.response.send_message(
                "サーバー内でのみ利用できます。", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            availability = await self.api.availability(actor, count=1)
            capabilities = await self.api.capabilities()
        except CafeApiError as exc:
            await _send_api_error(interaction, exc)
            return
        await _send_balance(
            interaction,
            availability=availability,
            hourly_limit=capabilities.hourly_draw_limit,
        )

    async def protection_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        actor = _actor(interaction)
        if actor is None:
            return []
        try:
            collection = await self.api.collection(actor)
        except CafeApiError:
            return []
        query = current.casefold().replace(" ", "").replace("　", "")
        ranked: list[tuple[int, int, CafeCollectionCard]] = []
        for index, card in enumerate(collection.cards):
            if card.count <= 0:
                continue
            name = card.name.casefold().replace(" ", "").replace("　", "")
            key = card.key.casefold()
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
            elif query in key:
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

    @app_commands.command(name="protect", description="所持カードの保護／解除を切替")
    @app_commands.describe(card="カード名を入力すると所持カードが候補表示されます")
    @app_commands.autocomplete(card=protection_autocomplete)
    async def protect(self, interaction: discord.Interaction, card: str) -> None:
        actor = _actor(interaction)
        if actor is None:
            await interaction.response.send_message(
                "サーバー内でのみ利用できます。", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            collection = await self.api.collection(actor)
            selected = next(
                (
                    item
                    for item in collection.cards
                    if item.count > 0
                    and (item.key == card or item.name.casefold() == card.casefold())
                ),
                None,
            )
            if selected is None:
                await interaction.followup.send(
                    "そのカードは現在所持していません。候補から選び直してください。",
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

    @app_commands.command(name="stats", description="利用状況とXP収支を管理者表示")
    @app_commands.default_permissions(administrator=True)
    async def stats(self, interaction: discord.Interaction) -> None:
        actor = _actor(interaction)
        if actor is None or not interaction.permissions.administrator:
            await interaction.response.send_message(
                "サーバー管理者権限が必要です。", ephemeral=True
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

    async def _access_role(
        self,
        interaction: discord.Interaction,
        *,
        action: Literal["add", "remove", "list"],
        role: discord.Role | None = None,
    ) -> None:
        actor = _actor(interaction)
        if actor is None or not interaction.permissions.administrator:
            await interaction.response.send_message(
                "サーバー管理者権限が必要です。", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
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
            message = (
                "カフェ・コレクションの利用ロール: "
                + " ".join(f"<@&{role_id}>" for role_id in result.role_ids)
                if result.role_ids
                else "利用ロールは未設定です。現在は全員が利用できます。"
            )
        elif action == "add" and role is not None:
            message = (
                f"利用ロールに {role.mention} を追加しました。"
                if result.changed
                else f"{role.mention} はすでに追加されています。"
            )
        elif role is not None:
            message = (
                f"利用ロールから {role.mention} を削除しました。"
                if result.changed
                else f"{role.mention} は設定されていません。"
            )
        else:  # pragma: no cover - command wiring always provides a role
            message = "ロールを指定してください。"
        await interaction.followup.send(
            message,
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @access_role.command(name="add", description="利用できるロールを追加")
    @app_commands.default_permissions(administrator=True)
    async def access_add(
        self, interaction: discord.Interaction, role: discord.Role
    ) -> None:
        await self._access_role(interaction, action="add", role=role)

    @access_role.command(name="remove", description="利用ロールを削除")
    @app_commands.default_permissions(administrator=True)
    async def access_remove(
        self, interaction: discord.Interaction, role: discord.Role
    ) -> None:
        await self._access_role(interaction, action="remove", role=role)

    @access_role.command(name="list", description="利用ロールを表示")
    @app_commands.default_permissions(administrator=True)
    async def access_list(self, interaction: discord.Interaction) -> None:
        await self._access_role(interaction, action="list")

    @app_commands.command(name="panel", description="このチャンネルに抽選パネルを設置")
    @app_commands.describe(channel="設置先（省略時は実行したチャンネル）")
    @app_commands.default_permissions(manage_guild=True)
    async def panel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
    ) -> None:
        await self._publish(interaction, channel=channel, placement="panel")

    @app_commands.command(name="ledger", description="このチャンネルを台帳に指定")
    @app_commands.describe(channel="指定先（省略時は実行したチャンネル）")
    @app_commands.default_permissions(manage_guild=True)
    async def ledger(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
    ) -> None:
        await self._publish(interaction, channel=channel, placement="ledger")

    @app_commands.command(name="ranking", description="ランキングパネルを設置")
    @app_commands.describe(channel="設置先（省略時は実行したチャンネル）")
    @app_commands.default_permissions(manage_guild=True)
    async def ranking(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
    ) -> None:
        await self._publish(interaction, channel=channel, placement="ranking")


async def setup(bot: commands.Bot) -> None:
    api = getattr(bot, "cafe_api", None)
    if not isinstance(api, CafeApiClient):
        raise RuntimeError("CafeApiClient is not configured")
    register_dynamic_items(bot)
    await bot.add_cog(CafeCog(api))
