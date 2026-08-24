"""Full Cafe collection, exchange, protection, medal, and set-menu UI."""

from __future__ import annotations

import asyncio
import logging
from io import BytesIO
from typing import Literal
from uuid import uuid4

import discord
from discord.ext import commands

from cafe_collection.collection_image import RARITY_LABELS, render_collection_pages
from cafe_collection.discord_context import (
    actor_from_interaction,
    api_from_interaction,
    ensure_feature_access,
    send_api_error,
)
from cafe_collection.ledger import publish_pending_for_guild
from cafe_collection.level_api import (
    CafeActor,
    CafeApiClient,
    CafeApiError,
    CafeCollection,
    CafeCollectionCard,
    CafeCosmetic,
)

RARITY_ORDER = ("C", "UC", "R", "SR", "SSR", "UR", "MYTHIC")
Action = Literal["favorite", "redeem_xp", "protect"]
RedemptionKind = Literal["xp", "medals"]
logger = logging.getLogger(__name__)
DEFAULT_EMBED_COLOR = 0x5865F2


def _rarity_label(value: str) -> str:
    return RARITY_LABELS.get(value, value)


def _collection_rarity_description(cards: list[CafeCollectionCard], rarity: str) -> str:
    lines = []
    for card in cards:
        if card.rarity != rarity or card.count <= 0:
            continue
        if card.is_protected and card.redeemable_count:
            state = f"（🔒重複 {card.redeemable_count}枚を保護）"
        elif card.is_protected:
            state = "（🔒保護中）"
        elif card.exchangeable_count:
            state = f"（交換可 {card.exchangeable_count}）"
        else:
            state = ""
        mastery = (
            f" · {card.mastery_emoji or ''}{card.mastery_name}"
            f"（累計{card.lifetime_count}枚）"
            if card.mastery_name is not None
            else ""
        )
        lines.append(f"**{card.name}** ×{card.count}{state}{mastery}")
    return "\n".join(lines) if lines else "このレアリティはまだ未収集です。"


def _actor_api(
    interaction: discord.Interaction,
) -> tuple[CafeActor, CafeApiClient] | None:
    actor = actor_from_interaction(interaction)
    api = api_from_interaction(interaction)
    return (actor, api) if actor is not None and api is not None else None


class UserView(discord.ui.View):
    def __init__(self, *, guild_id: int, user_id: int, timeout: float = 120) -> None:
        super().__init__(timeout=timeout)
        self.guild_id = guild_id
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "本人だけが操作できます。", ephemeral=True
            )
            return False
        if interaction.guild_id != self.guild_id:
            await interaction.response.send_message(
                "このサーバーでは利用できません。", ephemeral=True
            )
            return False
        context = _actor_api(interaction)
        if context is None:
            await interaction.response.send_message(
                "このサーバーでは利用できません。", ephemeral=True
            )
            return False
        actor, api = context
        return await ensure_feature_access(interaction, api, actor)


def _collection_summary(
    collection: CafeCollection,
    *,
    display_name: str,
) -> discord.Embed:
    owned = sum(card.count > 0 for card in collection.cards)
    progress = []
    for rarity in RARITY_ORDER:
        cards = [card for card in collection.cards if card.rarity == rarity]
        progress.append(
            f"{_rarity_label(rarity)} "
            f"{sum(card.count > 0 for card in cards)}/{len(cards)}"
        )
    cosmetic = collection.active_cosmetic
    embed = discord.Embed(
        title=(
            f"{cosmetic.decoration if cosmetic is not None else '🗃️'} "
            f"{display_name} のカード棚"
        ),
        description=(
            f"**レアリティ別収集**\n{' / '.join(progress)}\n\n"
            f"**N 所持カード**\n"
            f"{_collection_rarity_description(collection.cards, 'C')}"
            if owned
            else "まだカードはありません。"
        ),
        color=(cosmetic.color if cosmetic is not None else DEFAULT_EMBED_COLOR),
    )
    embed.add_field(
        name="🪙 カフェメダル",
        value=f"{collection.medal_balance:,}枚 · 重複カードから交換できます",
        inline=False,
    )
    favorite = next(
        (
            card
            for card in collection.cards
            if card.key == collection.favorite_reward_key
        ),
        None,
    )
    if favorite is not None:
        embed.add_field(
            name="お気に入りの一枚",
            value=f"{_rarity_label(favorite.rarity)}｜{favorite.name}",
        )
    embed.add_field(
        name="☕ カード熟練度",
        value=" / ".join(
            f"{tier.emoji}{tier.name} {tier.card_count}種"
            for tier in collection.mastery_tiers
        ),
        inline=False,
    )
    n_cards = [card for card in collection.cards if card.rarity == "C"]
    n_owned = sum(card.count > 0 for card in n_cards)
    if n_owned >= len(n_cards):
        milestone = "🏆 N棚の主"
        milestone_detail = f"Nカード全{len(n_cards)}種を収集しました。"
    elif n_owned >= 10:
        milestone = "🧺 N棚コレクター"
        milestone_detail = f"次の称号まであと {len(n_cards) - n_owned}種"
    elif n_owned >= 5:
        milestone = "☕ N棚見習い"
        milestone_detail = f"次の称号まであと {10 - n_owned}種"
    else:
        milestone = "N棚の入口"
        milestone_detail = f"最初の称号まであと {5 - n_owned}種"
    embed.add_field(
        name=milestone,
        value=f"N収集 {n_owned}/{len(n_cards)}種 · {milestone_detail}",
        inline=False,
    )
    exchangeable = sum(card.exchangeable_count for card in collection.cards)
    protected = sum(
        card.redeemable_count for card in collection.cards if card.is_protected
    )
    protected_text = (
        f" 保護中の重複 **{protected}枚** は交換対象外です。" if protected else ""
    )
    exchange_guidance = (
        f"交換可能なカードが合計 **{exchangeable}枚** あります。"
        "XPへの個別・全重複交換、またはカフェメダルへの全重複交換を選べます。"
        "どの交換でも各カードの最初の1枚は必ず残ります。" + protected_text
        if exchangeable
        else (
            "交換できる重複カードはまだありません。"
            "同じカードの2枚目以降がXP・メダル交換の対象になります。" + protected_text
        )
    )
    if collection.endgame_pity_active:
        embed.add_field(
            name="終盤のNEW保証",
            value=(
                f"NEWなし {collection.duplicate_draw_streak}/"
                f"{collection.endgame_pity_duplicate_draws}回\n"
                "上限まで続いた場合、次の抽選は未所持カードになります。"
            ),
            inline=False,
        )
    embed.add_field(name="XP交換", value=exchange_guidance, inline=False)
    embed.set_footer(
        text=(
            f"収集 {owned}/{len(collection.cards)}種 · "
            "最初の1枚と保護カードは残ります（交換対象は未保護の2枚目以降）"
        )
    )
    return embed


async def show_full_collection(
    interaction: discord.Interaction,
    *,
    api: CafeApiClient,
) -> None:
    actor = actor_from_interaction(interaction)
    if actor is None:
        await interaction.response.send_message(
            "このサーバーでは利用できません。", ephemeral=True
        )
        return
    if not await ensure_feature_access(interaction, api, actor):
        return
    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        collection = await api.collection(actor)
    except CafeApiError:
        await interaction.followup.send(
            "カード棚の読み込みに失敗しました。時間をおいてもう一度お試しください。",
            ephemeral=True,
        )
        return
    rendered: list[tuple[str, int, int, bytes]] = []
    try:
        for rarity in RARITY_ORDER:
            cards = [card for card in collection.cards if card.rarity == rarity]
            pages = await asyncio.to_thread(render_collection_pages, cards)
            rendered.extend(
                (rarity, page, len(pages), image)
                for page, image in enumerate(pages, start=1)
            )
    except (OSError, ValueError):
        logger.exception("Failed to render Cafe collection shelf")
        rendered = []
    embeds: list[discord.Embed] = []
    files: list[discord.File] = []
    summary = _collection_summary(
        collection,
        display_name=interaction.user.display_name,
    )
    try:
        if not rendered:
            embeds.append(summary)
        for index, (rarity, page, page_count, image) in enumerate(rendered):
            filename = f"collection-{rarity.lower()}-{page}.jpg"
            files.append(discord.File(BytesIO(image), filename=filename))
            if index == 0:
                embed = summary
            else:
                cards = [card for card in collection.cards if card.rarity == rarity]
                embed = discord.Embed(
                    title=(
                        f"{_rarity_label(rarity)} カード棚"
                        + (f" {page}/{page_count}" if page_count > 1 else "")
                    ),
                    description=(
                        f"所持 {sum(card.count > 0 for card in cards)}/{len(cards)}種"
                    ),
                    color=DEFAULT_EMBED_COLOR,
                )
            embed.set_image(url=f"attachment://{filename}")
            embed.set_footer(
                text=(
                    f"収集 {sum(card.count > 0 for card in collection.cards)}/"
                    f"{len(collection.cards)}種 · 最初の1枚と保護カードは残ります"
                    "（交換対象は未保護の2枚目以降）"
                )
            )
            embeds.append(embed)
        view = CollectionActionsView(
            guild_id=int(actor.guild_id),
            user_id=int(actor.user_id),
            collection=collection,
        )
        for start in range(0, len(embeds), 10):
            last = start + 10 >= len(embeds)
            if last:
                await interaction.followup.send(
                    embeds=embeds[start : start + 10],
                    files=files[start : start + 10],
                    view=view,
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    embeds=embeds[start : start + 10],
                    files=files[start : start + 10],
                    ephemeral=True,
                )
    finally:
        for file in files:
            file.close()


def _eligible_cards(
    collection: CafeCollection, action: Action
) -> list[CafeCollectionCard]:
    if action == "redeem_xp":
        return [card for card in collection.cards if card.exchangeable_count > 0]
    return [card for card in collection.cards if card.count > 0]


class ActionButton(discord.ui.Button[discord.ui.View]):
    def __init__(
        self,
        *,
        action: Action,
        collection: CafeCollection,
        row: int,
    ) -> None:
        labels = {
            "favorite": ("お気に入り", "⭐"),
            "redeem_xp": ("重複を選んでXP交換", "🎴"),
            "protect": ("カード保護（名前検索）", "🔒"),
        }
        label, emoji = labels[action]
        super().__init__(
            label=label,
            emoji=emoji,
            style=(
                discord.ButtonStyle.primary
                if action == "redeem_xp"
                else discord.ButtonStyle.secondary
            ),
            row=row,
        )
        self.action = action
        self.collection = collection

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.action == "protect":
            await interaction.response.send_message(
                "`/cafe-collection protect` のカード欄へ名前を入力してください。\n"
                "入力中に所持カードだけが候補表示され、同じコマンドで保護／解除できます。\n"
                "保護中のカードはXP・メダル交換から除外されます。",
                ephemeral=True,
            )
            return
        cards = _eligible_cards(self.collection, self.action)
        if not cards:
            await interaction.response.send_message(
                "対象になるカードがありません。", ephemeral=True
            )
            return
        await interaction.response.send_message(
            (
                "交換するカードのレアリティを選んでください。"
                if self.action == "redeem_xp"
                else "お気に入りにするカードのレアリティを選んでください。"
            ),
            view=RarityPageView(
                guild_id=interaction.guild_id or 0,
                user_id=interaction.user.id,
                cards=cards,
                action=self.action,
            ),
            ephemeral=True,
        )


class RarityPageSelect(discord.ui.Select[discord.ui.View]):
    def __init__(self, *, cards: list[CafeCollectionCard], action: Action) -> None:
        self.cards = cards
        self.action = action
        options: list[discord.SelectOption] = []
        for rarity in RARITY_ORDER:
            rarity_cards = [card for card in cards if card.rarity == rarity]
            page_count = (len(rarity_cards) + 24) // 25
            options.extend(
                discord.SelectOption(
                    label=(
                        f"{_rarity_label(rarity)}（{len(rarity_cards)}種）"
                        if page_count == 1
                        else (
                            f"{_rarity_label(rarity)}（{len(rarity_cards)}種・"
                            f"{page + 1}/{page_count}）"
                        )
                    ),
                    value=f"{rarity}:{page}",
                )
                for page in range(page_count)
            )
        action_label = {
            "favorite": "お気に入り",
            "redeem_xp": "交換",
            "protect": "保護設定",
        }[action]
        super().__init__(
            placeholder=f"{action_label}するカードのレアリティを選ぶ",
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        rarity, _, page_value = self.values[0].partition(":")
        page = int(page_value)
        cards = [card for card in self.cards if card.rarity == rarity]
        await interaction.response.send_message(
            {
                "favorite": "お気に入りにするカードを選んでください。",
                "redeem_xp": "交換するカードを1種類選んでください。",
                "protect": "保護または保護解除するカードを選んでください。",
            }[self.action],
            view=CardChoiceView(
                guild_id=interaction.guild_id or 0,
                user_id=interaction.user.id,
                cards=cards[page * 25 : (page + 1) * 25],
                action=self.action,
            ),
            ephemeral=True,
        )


class RarityPageView(UserView):
    def __init__(
        self,
        *,
        guild_id: int,
        user_id: int,
        cards: list[CafeCollectionCard],
        action: Action,
    ) -> None:
        super().__init__(guild_id=guild_id, user_id=user_id)
        self.add_item(RarityPageSelect(cards=cards, action=action))


class CardChoiceSelect(discord.ui.Select[discord.ui.View]):
    def __init__(self, *, cards: list[CafeCollectionCard], action: Action) -> None:
        self.cards_by_key = {card.key: card for card in cards}
        self.action = action
        super().__init__(
            placeholder={
                "favorite": "お気に入りの一枚を選ぶ",
                "redeem_xp": "交換するカードを1種類選ぶ",
                "protect": "保護設定を切り替えるカードを選ぶ",
            }[action],
            options=[
                discord.SelectOption(
                    label=(
                        f"{'🔒' if card.is_protected else '🔓'} {card.name}"
                        if action == "protect"
                        else f"{_rarity_label(card.rarity)}｜{card.name}"
                    )[:100],
                    value=card.key,
                    description=(
                        f"交換可 {card.exchangeable_count}枚 · "
                        f"1枚 {card.exchange_xp} XP"
                        if action == "redeem_xp"
                        else (
                            f"所持 {card.count}枚 · "
                            + (
                                "保護を解除"
                                if card.is_protected
                                else "重複を交換から保護"
                            )
                        )
                        if action == "protect"
                        else None
                    )[:100]
                    if action != "favorite"
                    else None,
                )
                for card in cards
            ],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        card = self.cards_by_key[self.values[0]]
        context = _actor_api(interaction)
        if context is None:
            await interaction.response.send_message(
                "このサーバーでは利用できません。", ephemeral=True
            )
            return
        actor, api = context
        if self.action == "redeem_xp":
            await interaction.response.send_message(
                f"**{_rarity_label(card.rarity)}｜{card.name}** "
                "の交換枚数を選んでください"
                f"（重複 {card.exchangeable_count}枚）。",
                view=QuantityView(
                    guild_id=int(actor.guild_id),
                    user_id=int(actor.user_id),
                    card=card,
                ),
                ephemeral=True,
            )
            return
        try:
            result = (
                await api.set_favorite(actor, reward_key=card.key)
                if self.action == "favorite"
                else await api.set_protection(
                    actor,
                    reward_key=card.key,
                    protected=not card.is_protected,
                )
            )
        except CafeApiError as exc:
            await send_api_error(interaction, exc)
            return
        if result.status != "updated":
            await interaction.response.send_message(
                (
                    "そのカードは現在所持していません。"
                    if self.action == "favorite"
                    else (
                        "そのカードは現在所持していません。"
                        "コレクションを開き直してください。"
                    )
                ),
                ephemeral=True,
            )
            return
        if self.action == "favorite":
            message = f"お気に入りの一枚を **{result.reward_name}** にしました。"
        elif result.protected:
            message = (
                f"🔒 **{result.reward_name}** を保護しました。"
                "今後のXP・メダル交換から除外します。"
            )
        else:
            message = f"🔓 **{result.reward_name}** の保護を解除しました。"
        await interaction.response.send_message(message, ephemeral=True)


class CardChoiceView(UserView):
    def __init__(
        self,
        *,
        guild_id: int,
        user_id: int,
        cards: list[CafeCollectionCard],
        action: Action,
    ) -> None:
        super().__init__(guild_id=guild_id, user_id=user_id)
        self.add_item(CardChoiceSelect(cards=cards, action=action))


class RedemptionConfirmView(UserView):
    def __init__(
        self,
        *,
        guild_id: int,
        user_id: int,
        quantities: dict[str, int],
        kind: RedemptionKind,
        confirm_label: str,
        unavailable_message: str,
    ) -> None:
        super().__init__(guild_id=guild_id, user_id=user_id)
        self.quantities = quantities
        self.kind = kind
        self.event_id = str(uuid4())
        self.unavailable_message = unavailable_message
        self.confirm.label = confirm_label
        if kind == "medals":
            self.remove_item(self.cancel)

    async def interaction_check(self, _interaction: discord.Interaction) -> bool:
        # Confirm/cancel intentionally have different ownership and access checks,
        # matching the existing bot's interaction behavior.
        return True

    @discord.ui.button(label="交換する", style=discord.ButtonStyle.danger)
    async def confirm(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button[discord.ui.View],
    ) -> None:
        if interaction.user.id != self.user_id or (
            self.kind == "xp" and interaction.guild is None
        ):
            await interaction.response.send_message(
                "本人だけが確定できます。", ephemeral=True
            )
            return
        context = _actor_api(interaction)
        if context is None:
            await interaction.response.send_message(
                "このサーバーでは利用できません。", ephemeral=True
            )
            return
        actor, api = context
        if int(actor.guild_id) != self.guild_id:
            await interaction.response.send_message(
                "このサーバーでは利用できません。", ephemeral=True
            )
            return
        if not await ensure_feature_access(interaction, api, actor):
            return
        await interaction.response.edit_message(content="交換しています…", view=None)
        try:
            result = (
                await api.redeem_xp(
                    actor,
                    event_id=self.event_id,
                    display_name=interaction.user.display_name,
                    quantities=self.quantities,
                )
                if self.kind == "xp"
                else await api.redeem_medals(
                    actor,
                    event_id=self.event_id,
                    display_name=interaction.user.display_name,
                    quantities=self.quantities,
                )
            )
        except CafeApiError as exc:
            await send_api_error(interaction, exc)
            return
        self.stop()
        if result.status != "redeemed":
            await interaction.followup.send(
                self.unavailable_message,
                ephemeral=True,
            )
            return
        if (
            self.kind == "xp"
            and interaction.guild is not None
            and isinstance(interaction.client, commands.Bot)
        ):
            try:
                await publish_pending_for_guild(
                    interaction.client, api, interaction.guild
                )
            except CafeApiError:
                logger.exception(
                    "Failed to publish Cafe ledger for guild %s",
                    interaction.guild.id,
                )
        message = (
            f"{result.reward_xp:,} XP を受け取りました。"
            if self.kind == "xp"
            else (
                f"☕ **{result.reward_medals:,}メダル**を受け取りました。\n"
                f"現在: **{result.medal_balance or 0:,}メダル**"
            )
        )
        await interaction.followup.send(message, ephemeral=True)

    @discord.ui.button(label="キャンセル", style=discord.ButtonStyle.secondary)
    async def cancel(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button[discord.ui.View],
    ) -> None:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "本人だけが操作できます。", ephemeral=True
            )
            return
        await interaction.response.edit_message(
            content="交換をキャンセルしました。", view=None
        )
        self.stop()


async def _send_redemption_confirmation(
    interaction: discord.Interaction,
    *,
    card: CafeCollectionCard,
    quantity: int,
) -> None:
    reward = card.exchange_xp * quantity
    await interaction.response.send_message(
        (
            f"**{_rarity_label(card.rarity)}｜{card.name} × {quantity}枚** "
            "を交換します。\n"
            f"所持: {card.count} → **{card.count - quantity}枚**\n"
            f"受取: **{reward:,} XP**\n"
            "コレクション用の最初の1枚は残ります。"
        ),
        view=RedemptionConfirmView(
            guild_id=interaction.guild_id or 0,
            user_id=interaction.user.id,
            quantities={card.key: quantity},
            kind="xp",
            confirm_label="このカードを交換する",
            unavailable_message=(
                "重複枚数が変わったため交換できませんでした。"
                "コレクションを開き直してください。"
            ),
        ),
        ephemeral=True,
    )


class CustomQuantityModal(discord.ui.Modal, title="交換する重複枚数"):
    quantity: discord.ui.TextInput[CustomQuantityModal] = discord.ui.TextInput(
        label="枚数", placeholder="1", min_length=1, max_length=4
    )

    def __init__(
        self,
        *,
        guild_id: int,
        user_id: int,
        card: CafeCollectionCard,
    ) -> None:
        super().__init__()
        self.guild_id = guild_id
        self.user_id = user_id
        self.card = card

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "本人だけが操作できます。", ephemeral=True
            )
            return
        context = _actor_api(interaction)
        if context is None or int(context[0].guild_id) != self.guild_id:
            await interaction.response.send_message(
                "このサーバーでは利用できません。", ephemeral=True
            )
            return
        actor, api = context
        if not await ensure_feature_access(interaction, api, actor):
            return
        try:
            quantity = int(self.quantity.value)
        except ValueError:
            quantity = 0
        if not 1 <= quantity <= self.card.exchangeable_count:
            await interaction.response.send_message(
                f"1〜{self.card.exchangeable_count} の枚数を入力してください。",
                ephemeral=True,
            )
            return
        await _send_redemption_confirmation(
            interaction,
            card=self.card,
            quantity=quantity,
        )


class QuantityView(UserView):
    def __init__(
        self,
        *,
        guild_id: int,
        user_id: int,
        card: CafeCollectionCard,
    ) -> None:
        super().__init__(guild_id=guild_id, user_id=user_id)
        self.card = card

    @discord.ui.button(label="このカードを1枚交換", style=discord.ButtonStyle.primary)
    async def one(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button[discord.ui.View],
    ) -> None:
        await _send_redemption_confirmation(interaction, card=self.card, quantity=1)

    @discord.ui.button(
        label="このカードの重複を全交換",
        style=discord.ButtonStyle.secondary,
    )
    async def all_duplicates(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button[discord.ui.View],
    ) -> None:
        await _send_redemption_confirmation(
            interaction,
            card=self.card,
            quantity=self.card.exchangeable_count,
        )

    @discord.ui.button(
        label="このカードの枚数を指定",
        style=discord.ButtonStyle.secondary,
    )
    async def custom(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button[discord.ui.View],
    ) -> None:
        await interaction.response.send_modal(
            CustomQuantityModal(
                guild_id=self.guild_id,
                user_id=self.user_id,
                card=self.card,
            )
        )


class BulkExchangeButton(discord.ui.Button[discord.ui.View]):
    def __init__(self, *, collection: CafeCollection, kind: RedemptionKind) -> None:
        self.collection = collection
        self.kind = kind
        label = "全重複をXP交換" if kind == "xp" else "全重複をメダル交換"
        emoji = "♻️" if kind == "xp" else "☕"
        super().__init__(
            label=label,
            emoji=emoji,
            style=(
                discord.ButtonStyle.success
                if kind == "xp"
                else discord.ButtonStyle.secondary
            ),
            row=1 if kind == "xp" else 2,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        quantities = {
            card.key: card.exchangeable_count
            for card in self.collection.cards
            if card.exchangeable_count > 0
        }
        if not quantities:
            await interaction.response.send_message(
                "交換できる重複カードがありません。", ephemeral=True
            )
            return
        if self.kind == "xp":
            reward = sum(
                card.exchange_xp * card.exchangeable_count
                for card in self.collection.cards
            )
            details = []
            for rarity in RARITY_ORDER:
                cards = [
                    card
                    for card in self.collection.cards
                    if card.rarity == rarity and card.exchangeable_count > 0
                ]
                if not cards:
                    continue
                quantity = sum(card.exchangeable_count for card in cards)
                reward_xp = sum(
                    card.exchange_xp * card.exchangeable_count for card in cards
                )
                details.append(
                    f"{_rarity_label(rarity)}: {len(cards)}種・{quantity}枚 "
                    f"→ {reward_xp:,} XP"
                )
            content = (
                "交換可能な重複カードをすべてXPへ交換します。\n"
                + "\n".join(details)
                + "\n**各カードの最初の1枚と保護カードは残ります。**"
                + f"\n\n受取合計: **{reward:,} XP**"
            )
            confirm_label = "全重複をXPへ交換する"
            unavailable_message = (
                "所持数が変わったため交換できませんでした。"
                "コレクションを開き直してください。"
            )
        else:
            reward = sum(
                card.exchange_medals * card.exchangeable_count
                for card in self.collection.cards
            )
            content = (
                f"全カードの重複を **{reward:,}カフェメダル**へ交換します。\n"
                "XPには交換されません。最初の1枚と保護カードは残ります。"
            )
            confirm_label = "メダルへ交換する"
            unavailable_message = "所持数が変わったため交換できませんでした。"
        await interaction.response.send_message(
            content,
            view=RedemptionConfirmView(
                guild_id=interaction.guild_id or 0,
                user_id=interaction.user.id,
                quantities=quantities,
                kind=self.kind,
                confirm_label=confirm_label,
                unavailable_message=unavailable_message,
            ),
            ephemeral=True,
        )


class CosmeticSelect(discord.ui.Select[discord.ui.View]):
    def __init__(self, *, cosmetics: list[CafeCosmetic]) -> None:
        self.cosmetics = {item.key: item for item in cosmetics}
        super().__init__(
            placeholder="購入・装備する棚テーマを選ぶ",
            options=[
                discord.SelectOption(
                    label=item.name,
                    value=item.key,
                    description=f"{item.cost_medals:,}カフェメダル",
                    emoji=item.decoration,
                )
                for item in cosmetics
            ],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        cosmetic = self.cosmetics[self.values[0]]
        await interaction.response.send_message(
            (
                f"**{cosmetic.name}**（{cosmetic.cost_medals:,}メダル）を購入・装備します。\n"
                "購入済みの場合は再徴収されません。"
            ),
            view=CosmeticConfirmView(
                guild_id=interaction.guild_id or 0,
                user_id=interaction.user.id,
                cosmetic=cosmetic,
            ),
            ephemeral=True,
        )


class CosmeticSelectView(UserView):
    def __init__(
        self,
        *,
        guild_id: int,
        user_id: int,
        cosmetics: list[CafeCosmetic],
    ) -> None:
        super().__init__(guild_id=guild_id, user_id=user_id)
        self.add_item(CosmeticSelect(cosmetics=cosmetics))


class CosmeticConfirmView(UserView):
    def __init__(
        self,
        *,
        guild_id: int,
        user_id: int,
        cosmetic: CafeCosmetic,
    ) -> None:
        super().__init__(guild_id=guild_id, user_id=user_id)
        self.cosmetic = cosmetic

    async def interaction_check(self, _interaction: discord.Interaction) -> bool:
        return True

    @discord.ui.button(label="購入・装備する", style=discord.ButtonStyle.primary)
    async def confirm(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button[discord.ui.View],
    ) -> None:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "本人だけが確定できます。", ephemeral=True
            )
            return
        context = _actor_api(interaction)
        if context is None:
            await interaction.response.send_message(
                "このサーバーでは利用できません。", ephemeral=True
            )
            return
        actor, api = context
        if int(actor.guild_id) != self.guild_id:
            await interaction.response.send_message(
                "このサーバーでは利用できません。", ephemeral=True
            )
            return
        if not await ensure_feature_access(interaction, api, actor):
            return
        await interaction.response.edit_message(
            content="棚テーマを確認しています…", view=None
        )
        self.stop()
        try:
            result = await api.equip_cosmetic(actor, cosmetic_key=self.cosmetic.key)
        except CafeApiError as exc:
            await send_api_error(interaction, exc)
            return
        if result.status == "insufficient":
            message = f"メダルが足りません。現在 **{result.balance:,}メダル**です。"
        elif result.status == "equipped" and result.cosmetic is not None:
            message = (
                f"{result.cosmetic.decoration} **{result.cosmetic.name}**を"
                "装備しました。\n"
                f"残り **{result.balance:,}メダル**"
            )
        else:
            message = "棚テーマが見つかりません。"
        await interaction.followup.send(message, ephemeral=True)


class ThemeButton(discord.ui.Button[discord.ui.View]):
    def __init__(self, *, collection: CafeCollection) -> None:
        super().__init__(label="メダル・棚テーマ", emoji="🪙", row=2)
        self.collection = collection

    async def callback(self, interaction: discord.Interaction) -> None:
        context = _actor_api(interaction)
        if context is None:
            await interaction.response.send_message(
                "このサーバーでは利用できません。", ephemeral=True
            )
            return
        actor, api = context
        try:
            collection = await api.collection(actor)
        except CafeApiError as exc:
            await send_api_error(interaction, exc)
            return
        await interaction.response.send_message(
            (
                f"現在 **{collection.medal_balance:,}カフェメダル**です。"
                "棚テーマを選んでください。"
            ),
            view=CosmeticSelectView(
                guild_id=interaction.guild_id or 0,
                user_id=interaction.user.id,
                cosmetics=collection.cosmetics,
            ),
            ephemeral=True,
        )


class MossProtectionButton(discord.ui.Button[discord.ui.View]):
    def __init__(self, *, card: CafeCollectionCard) -> None:
        self.card = card
        self.target_protected = not card.is_protected
        super().__init__(
            label=("苔コーラを保護" if self.target_protected else "苔コーラの保護解除"),
            emoji="🥤",
            style=(
                discord.ButtonStyle.success
                if self.target_protected
                else discord.ButtonStyle.secondary
            ),
            row=3,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        context = _actor_api(interaction)
        if context is None:
            await interaction.response.send_message(
                "このサーバーでは利用できません。", ephemeral=True
            )
            return
        actor, api = context
        try:
            result = await api.set_protection(
                actor,
                reward_key=self.card.key,
                protected=self.target_protected,
            )
        except CafeApiError as exc:
            await send_api_error(interaction, exc)
            return
        message = (
            "🔒 **苔コーラ**を保護しました。今後のXP・メダル交換から除外します。"
            if result.status == "updated" and self.target_protected
            else "🔓 **苔コーラ**の保護を解除しました。"
            if result.status == "updated"
            else "苔コーラを現在所持していません。棚を開き直してください。"
        )
        await interaction.response.send_message(message, ephemeral=True)


def _set_embed(collection: CafeCollection, page: int) -> discord.Embed:
    page_size = 10
    page_count = max(1, (len(collection.sets) + page_size - 1) // page_size)
    embed = discord.Embed(
        title="🍽️ セットメニュー帳",
        description=(
            f"完成 **{sum(item.completed for item in collection.sets)}/"
            f"{len(collection.sets)}セット**\n"
            "一度でも引いたカードで判定するため、重複交換後も達成は消えません。"
        ),
        color=DEFAULT_EMBED_COLOR,
    )
    for item in collection.sets[page * page_size : (page + 1) * page_size]:
        embed.add_field(
            name=f"{'✅' if item.completed else '⬜'} {item.name}",
            value=(
                f"{item.description}\n"
                + (
                    "完成済み"
                    if item.completed
                    else f"あと: {'、'.join(item.missing_card_names)}"
                )
            ),
            inline=False,
        )
    embed.set_footer(text=f"ページ {page + 1}/{page_count}")
    return embed


class SetMenuView(UserView):
    def __init__(
        self,
        *,
        guild_id: int,
        user_id: int,
        collection: CafeCollection,
        page: int,
    ) -> None:
        super().__init__(guild_id=guild_id, user_id=user_id)
        self.collection = collection
        self.page = page
        page_count = max(1, (len(collection.sets) + 9) // 10)
        self.previous.disabled = page == 0
        self.next.disabled = page == page_count - 1

    async def _show(self, interaction: discord.Interaction, page: int) -> None:
        await interaction.response.edit_message(
            embed=_set_embed(self.collection, page),
            view=SetMenuView(
                guild_id=self.guild_id,
                user_id=self.user_id,
                collection=self.collection,
                page=page,
            ),
        )

    @discord.ui.button(label="前へ", style=discord.ButtonStyle.secondary)
    async def previous(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button[discord.ui.View],
    ) -> None:
        await self._show(interaction, self.page - 1)

    @discord.ui.button(label="次へ", style=discord.ButtonStyle.secondary)
    async def next(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button[discord.ui.View],
    ) -> None:
        await self._show(interaction, self.page + 1)


class SetMenuButton(discord.ui.Button[discord.ui.View]):
    def __init__(self, *, collection: CafeCollection) -> None:
        super().__init__(label="セットメニュー", emoji="🍽️", row=3)
        self.collection = collection

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            embed=_set_embed(self.collection, 0),
            view=SetMenuView(
                guild_id=interaction.guild_id or 0,
                user_id=interaction.user.id,
                collection=self.collection,
                page=0,
            ),
            ephemeral=True,
        )


class CollectionActionsView(UserView):
    def __init__(
        self,
        *,
        guild_id: int,
        user_id: int,
        collection: CafeCollection,
    ) -> None:
        super().__init__(guild_id=guild_id, user_id=user_id, timeout=180)
        owned_cards = [card for card in collection.cards if card.count > 0]
        if owned_cards:
            self.add_item(RarityPageSelect(cards=owned_cards, action="favorite"))
        if any(card.exchangeable_count > 0 for card in collection.cards):
            self.add_item(
                ActionButton(action="redeem_xp", collection=collection, row=1)
            )
            self.add_item(BulkExchangeButton(collection=collection, kind="xp"))
            self.add_item(BulkExchangeButton(collection=collection, kind="medals"))
        self.add_item(ThemeButton(collection=collection))
        moss_cola = next(
            (
                card
                for card in collection.cards
                if card.key == "moss-cola" and card.count > 0
            ),
            None,
        )
        if moss_cola is not None:
            self.add_item(MossProtectionButton(card=moss_cola))
        if owned_cards:
            self.add_item(ActionButton(action="protect", collection=collection, row=3))
        self.add_item(SetMenuButton(collection=collection))
