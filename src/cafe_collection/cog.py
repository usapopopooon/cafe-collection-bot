"""Discord commands backed by level-bot's transactional Cafe API."""

from __future__ import annotations

import asyncio
from io import BytesIO

import discord
from discord import app_commands
from discord.ext import commands

from cafe_collection.assets import card_image_path
from cafe_collection.collection_image import RARITY_LABELS, render_collection_pages
from cafe_collection.level_api import (
    CafeAccessDenied,
    CafeActor,
    CafeApiClient,
    CafeApiError,
    CafeDrawBatch,
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


def _actor(interaction: discord.Interaction) -> CafeActor | None:
    if interaction.guild is None:
        return None
    role_ids = (
        [str(role.id) for role in interaction.user.roles]
        if isinstance(interaction.user, discord.Member)
        else []
    )
    return CafeActor(
        guild_id=str(interaction.guild.id),
        user_id=str(interaction.user.id),
        role_ids=role_ids,
        can_manage_guild=(
            interaction.permissions.administrator
            or interaction.permissions.manage_guild
        ),
    )


async def _send_api_error(
    interaction: discord.Interaction, error: CafeApiError
) -> None:
    message = (
        str(error)
        if isinstance(error, CafeAccessDenied)
        else "カフェのデータサービスへ接続できません。少し待ってからお試しください。"
    )
    await interaction.followup.send(
        message,
        ephemeral=True,
        allowed_mentions=discord.AllowedMentions.none(),
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
                "結果は旧Botのカフェ台帳にも順次反映されます。"
            ),
            embeds=embeds,
            files=files,
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )
    finally:
        for file in files:
            file.close()


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


class CafeCog(
    commands.GroupCog, group_name="cafe", group_description="カフェ・コレクション"
):
    def __init__(self, api: CafeApiClient) -> None:
        self.api = api

    @app_commands.command(name="draw", description="カフェカードを1〜10枚引きます")
    @app_commands.describe(count="引く枚数（1〜10枚）")
    async def draw(
        self,
        interaction: discord.Interaction,
        count: app_commands.Range[int, 1, 10] = 1,
    ) -> None:
        actor = _actor(interaction)
        if actor is None:
            await interaction.response.send_message(
                "サーバー内でのみ利用できます。", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            availability = await self.api.availability(actor, count=count)
        except CafeApiError as exc:
            await _send_api_error(interaction, exc)
            return
        if count > availability.hourly_remaining:
            await interaction.followup.send(
                f"この時間の残り枠は **{availability.hourly_remaining}回** です。",
                ephemeral=True,
            )
            return
        event_id = f"cafe-bot:{interaction.id}"
        if availability.cost_xp == 0:
            try:
                result = await self.api.draw(
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
            return
        view = DrawConfirmView(
            api=self.api,
            actor=actor,
            requester_id=interaction.user.id,
            event_id=event_id,
            display_name=interaction.user.display_name,
            count=count,
            expected_cost_xp=availability.cost_xp,
        )
        await interaction.followup.send(
            (
                f"**{count}枚**引きます。\n"
                f"現在XP: **{availability.wallet.available_xp:,} XP**\n"
                f"消費XP: **{availability.cost_xp:,} XP**\n"
                f"この時間の残り枠: {availability.hourly_remaining}回"
            ),
            view=view,
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @app_commands.command(
        name="collection", description="レアリティ別のカード棚を表示します"
    )
    @app_commands.choices(rarity=RARITY_CHOICES)
    async def collection(
        self,
        interaction: discord.Interaction,
        rarity: app_commands.Choice[str],
    ) -> None:
        actor = _actor(interaction)
        if actor is None:
            await interaction.response.send_message(
                "サーバー内でのみ利用できます。", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            collection = await self.api.collection(actor)
        except CafeApiError as exc:
            await _send_api_error(interaction, exc)
            return
        cards = [card for card in collection.cards if card.rarity == rarity.value]
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
                filename = f"collection-{rarity.value.lower()}-{page_number}.jpg"
                files.append(discord.File(BytesIO(image), filename=filename))
                embed = discord.Embed(
                    title=f"☕ カフェカード棚｜{rarity.name}",
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


async def setup(bot: commands.Bot) -> None:
    api = getattr(bot, "cafe_api", None)
    if not isinstance(api, CafeApiClient):
        raise RuntimeError("CafeApiClient is not configured")
    await bot.add_cog(CafeCog(api))
