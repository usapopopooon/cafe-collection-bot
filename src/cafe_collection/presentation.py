"""Discord presentation for the separately deployed Cafe bot."""

from __future__ import annotations

from dataclasses import dataclass
from zoneinfo import ZoneInfo

import discord

from cafe_collection.level_api import (
    CafeAnalytics,
    CafeCapabilities,
    CafeRankingCategory,
    CafeRankingEntry,
    CafeRankings,
)

PANEL_TITLE = "☕ カフェ・コレクション"
LEDGER_TITLE = "📒 カフェ台帳"
RANKING_TITLE = "🏆 カフェ・コレクションランキング"
CAFE_COLLECTION_SITE_URL = "https://chill-cafe.site/cafe-collection/"
CAFE_RANKINGS_SITE_URL = f"{CAFE_COLLECTION_SITE_URL}rankings/"
TOKYO = ZoneInfo("Asia/Tokyo")


@dataclass(frozen=True)
class CategoryPresentation:
    label: str
    emoji: str


CATEGORY_PRESENTATIONS: dict[str, CategoryPresentation] = {
    "collection": CategoryPresentation("図鑑", "📚"),
    "mastery": CategoryPresentation("熟練度", "☕"),
    "sets": CategoryPresentation("セット", "🍽️"),
    "rare": CategoryPresentation("レア棚", "✨"),
    "treasure": CategoryPresentation("秘宝棚", "💎"),
    "joke": CategoryPresentation("ネタ棚", "😂"),
    "coffee": CategoryPresentation("珈琲通", "🫘"),
    "tea": CategoryPresentation("茶の達人", "🍵"),
    "sweets": CategoryPresentation("甘味通", "🍰"),
    "culture": CategoryPresentation("食文化探訪", "🏺"),
}


def build_panel_embed(capabilities: CafeCapabilities) -> discord.Embed:
    embed = discord.Embed(
        title=PANEL_TITLE,
        description=(
            "同じカード・XPを旧Botと共有しながら遊べます。\n\n"
            f"**1日1枚無料** / 以降1枚 **{capabilities.paid_draw_cost_xp} XP** / "
            f"1時間 **{capabilities.hourly_draw_limit}枚**まで\n"
            f"1枚につき **{capabilities.minimum_draw_reward_xp}〜"
            f"{capabilities.maximum_draw_reward_xp} XP**を獲得します。\n\n"
            "抽選は1操作につき1回だけ確定し、結果は指定されたカフェ台帳へ順次投稿されます。"
        ),
        color=discord.Color.from_rgb(139, 90, 60),
    )
    embed.set_image(url="attachment://panel-cabinet.jpg")
    embed.set_footer(text="旧Botとの併用中も抽選状態は共通です")
    return embed


def build_ledger_embed() -> discord.Embed:
    return discord.Embed(
        title=LEDGER_TITLE,
        description=(
            "このチャンネルをカフェ台帳に指定しました。\n"
            "両Botの抽選結果は、共通データから重複なくここへ投稿されます。"
        ),
        color=discord.Color.from_rgb(92, 64, 51),
    )


def _metric(entry: CafeRankingEntry, category: str) -> str:
    if category == "collection":
        return f"{entry.collection_count}種"
    if category == "mastery":
        return f"{entry.mastery_score:,} pt（看板 {entry.signature_cards}）"
    if category == "sets":
        return f"{entry.completed_sets}セット"
    if category == "rare":
        return f"{entry.rare_collection_count}種"
    if category == "treasure":
        return f"{entry.treasure_collection_count}種"
    if category == "joke":
        return f"{entry.n_mastery_score:,} pt"
    value = {
        "coffee": entry.coffee_mastery_score,
        "tea": entry.tea_mastery_score,
        "sweets": entry.sweets_mastery_score,
        "culture": entry.culture_mastery_score,
    }.get(category, 0)
    return f"{value:,} pt"


def _line(entry: CafeRankingEntry, category: str) -> str:
    prefix = {1: "🥇", 2: "🥈", 3: "🥉"}.get(entry.rank, f"**#{entry.rank}**")
    return f"{prefix} <@{entry.user_id}> — **{_metric(entry, category)}**"


def _category(rankings: CafeRankings, key: str) -> CafeRankingCategory | None:
    return next(
        (category for category in rankings.categories if category.key == key), None
    )


def build_ranking_panel_embed(rankings: CafeRankings) -> discord.Embed:
    embed = discord.Embed(
        title=RANKING_TITLE,
        description=(
            f"参加者 **{rankings.participant_count}人** / "
            f"累計抽選 **{rankings.total_draws:,}回**\n"
            "各ボタンでTOP 20を表示します。"
        ),
        color=discord.Color.from_rgb(181, 140, 52),
    )
    for key, presentation in CATEGORY_PRESENTATIONS.items():
        category = _category(rankings, key)
        lines = (
            [_line(entry, key) for entry in category.entries[:3]]
            if category is not None
            else []
        )
        embed.add_field(
            name=f"{presentation.emoji} {presentation.label} TOP 3",
            value="\n".join(lines) if lines else "まだ抽選記録がありません。",
            inline=False,
        )
    updated = rankings.captured_at.astimezone(TOKYO).strftime("%m/%d %H:%M")
    embed.set_footer(text=f"ボタン操作時に更新 · 最終集計 {updated} JST")
    return embed


def build_ranking_detail_embed(
    rankings: CafeRankings,
    *,
    category_key: str,
    viewer_id: str,
) -> discord.Embed:
    presentation = CATEGORY_PRESENTATIONS[category_key]
    category = _category(rankings, category_key)
    entries = category.entries if category is not None else []
    lines = [_line(entry, category_key) for entry in entries]
    embed = discord.Embed(
        title=f"{presentation.emoji} {presentation.label}ランキング",
        description="\n".join(lines) if lines else "まだ抽選記録がありません。",
        color=discord.Color.from_rgb(181, 140, 52),
    )
    viewer = (
        category.viewer_entry
        if category is not None and category.viewer_entry is not None
        else next((entry for entry in entries if entry.user_id == viewer_id), None)
    )
    embed.add_field(
        name="あなたの順位",
        value=(
            _line(viewer, category_key)
            if viewer is not None
            else "TOP 20圏外または抽選記録がありません。"
        ),
        inline=False,
    )
    return embed


def build_analytics_embed(
    analytics: CafeAnalytics,
    *,
    catalog_size: int,
) -> discord.Embed:
    week_new_rate = (
        analytics.new_7d / analytics.draws_7d * 100 if analytics.draws_7d else 0.0
    )
    rarity_labels = {"C": "N", "UC": "HN", "MYTHIC": "幻"}
    rarity_order = ("C", "UC", "R", "SR", "SSR", "UR", "MYTHIC")
    rarity_text = " / ".join(
        f"{rarity_labels.get(rarity, rarity)} {analytics.rarity_7d.get(rarity, 0):,}"
        for rarity in rarity_order
    )
    net_xp = (
        analytics.draw_reward_xp_7d + analytics.redemption_xp_7d - analytics.spent_xp_7d
    )
    embed = discord.Embed(
        title="📊 カフェ・コレクション利用状況",
        description="管理者だけに表示されます。日付境界は日本時間 0:00 です。",
        color=discord.Color.from_rgb(139, 90, 60),
    )
    embed.add_field(
        name="抽選数",
        value=(
            f"本日 **{analytics.draws_today:,}回** / "
            f"7日 **{analytics.draws_7d:,}回** / "
            f"累計 **{analytics.total_draws:,}回**"
        ),
        inline=False,
    )
    embed.add_field(
        name="利用者",
        value=(
            f"本日 **{analytics.active_today:,}人** / "
            f"7日 **{analytics.active_7d:,}人** / "
            f"累計 **{analytics.total_users:,}人**\n"
            f"全{catalog_size}種コンプリート **{analytics.completed_users:,}人**"
        ),
        inline=False,
    )
    embed.add_field(
        name="直近7日の収集状況",
        value=(
            f"NEW **{analytics.new_7d:,}回** ({week_new_rate:.1f}%) / "
            f"重複 **{analytics.duplicate_7d:,}回**\n{rarity_text}"
        ),
        inline=False,
    )
    embed.add_field(
        name="直近7日のXP収支",
        value=(
            f"抽選消費 {analytics.spent_xp_7d:,} / "
            f"抽選獲得 {analytics.draw_reward_xp_7d:,} / "
            f"重複交換 {analytics.redemption_xp_7d:,}\n"
            f"ユーザー側の純増 **{net_xp:+,} XP**"
        ),
        inline=False,
    )
    return embed
