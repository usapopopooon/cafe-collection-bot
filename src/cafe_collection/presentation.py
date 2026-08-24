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
RANKING_TITLE = "☕ カフェ・コレクションランキング"
CAFE_COLLECTION_SITE_URL = "https://chill-cafe.site/cafe-collection/"
CAFE_RANKINGS_SITE_URL = f"{CAFE_COLLECTION_SITE_URL}rankings/"
TOKYO = ZoneInfo("Asia/Tokyo")
DEFAULT_EMBED_COLOR = 0x5865F2
RARITY_ORDER = ("C", "UC", "R", "SR", "SSR", "UR", "MYTHIC")
RARITY_LABELS = {"C": "N", "UC": "HN", "MYTHIC": "幻"}


@dataclass(frozen=True)
class CategoryPresentation:
    button_label: str
    emoji: str
    title: str
    explanation: str
    tiebreaker: str


CATEGORY_PRESENTATIONS: dict[str, CategoryPresentation] = {
    "collection": CategoryPresentation(
        "図鑑",
        "📚",
        "図鑑ランキング",
        "異なるカードの収集種類数を競います。",
        "同数の場合はレア棚、セット、熟練度の順で決まります。",
    ),
    "mastery": CategoryPresentation(
        "熟練度",
        "☕",
        "熟練度ランキング",
        "各カードの最高熟練度（発見1・なじみ3・常連10・看板25 pt）を合計します。",
        "同点の場合は図鑑収集数、累計抽選数の順で決まります。",
    ),
    "sets": CategoryPresentation(
        "セット",
        "🍽️",
        "セットメニューランキング",
        "完成したセットメニュー数を競います。",
        "同数の場合は図鑑収集数、熟練度の順で決まります。",
    ),
    "rare": CategoryPresentation(
        "レア棚",
        "💎",
        "レア棚ランキング",
        "R・SR・SSR・UR・幻の異なるカード種類数を競います。",
        "同数の場合は幻、UR、図鑑収集数、熟練度の順で決まります。",
    ),
    "treasure": CategoryPresentation(
        "秘宝棚",
        "🏛️",
        "秘宝棚ランキング",
        "UR・幻だけの異なるカード種類数を競います。",
        "同数の場合は幻、UR、図鑑収集数、熟練度の順で決まります。",
    ),
    "joke": CategoryPresentation(
        "ネタ棚",
        "🥖",
        "ネタ棚ランキング",
        "Nカードだけの熟練ポイント（発見1〜看板25 pt）を競います。",
        "同点の場合はN収集数、全図鑑収集数の順で決まります。",
    ),
    "coffee": CategoryPresentation(
        "珈琲通",
        "🫘",
        "珈琲通ランキング",
        "珈琲・代用珈琲・産地銘柄などの熟練ポイントを競います。",
        "同点の場合は看板数、対象カード収集数、全熟練度の順で決まります。",
    ),
    "tea": CategoryPresentation(
        "茶の達人",
        "🍵",
        "茶の達人ランキング",
        "紅茶・日本茶・中国茶・発酵茶などの熟練ポイントを競います。",
        "同点の場合は看板数、対象カード収集数、全熟練度の順で決まります。",
    ),
    "sweets": CategoryPresentation(
        "甘味通",
        "🍰",
        "甘味通ランキング",
        "菓子・デザート系カードの熟練ポイントを競います。",
        "同点の場合は看板数、対象カード収集数、全熟練度の順で決まります。",
    ),
    "culture": CategoryPresentation(
        "食文化探訪",
        "🏺",
        "食文化探訪ランキング",
        "歴史食・代用食・土地の食文化を伝えるカードの熟練ポイントを競います。",
        "同点の場合は看板数、対象カード収集数、全熟練度の順で決まります。",
    ),
}


def build_panel_embed(capabilities: CafeCapabilities) -> discord.Embed:
    paid_profit = capabilities.minimum_draw_reward_xp - capabilities.paid_draw_cost_xp
    draw_xp = " / ".join(
        f"{RARITY_LABELS.get(rarity, rarity)} "
        f"{capabilities.draw_reward_xp_by_rarity[rarity]}"
        for rarity in RARITY_ORDER
    )
    exchange_xp = " / ".join(
        f"{RARITY_LABELS.get(rarity, rarity)} "
        f"{capabilities.exchange_xp_by_rarity[rarity]}"
        for rarity in RARITY_ORDER
    )
    embed = discord.Embed(
        title=PANEL_TITLE,
        description=(
            "カードを集めながら、**引くたびXPが必ず増える**コレクションです。\n\n"
            f"**🎟️ 1日1回無料** / 2回目以降 "
            f"{capabilities.paid_draw_cost_xp} XP / "
            f"1時間{capabilities.hourly_draw_limit}回まで / "
            "**1日の合計上限なし**\n"
            f"**必ず黒字：{capabilities.minimum_draw_reward_xp}〜"
            f"{capabilities.maximum_draw_reward_xp} XP獲得**"
            f"（有料でも +{paid_profit} XP以上）\n\n"
            f"**✨ 抽選の獲得XP**　{draw_xp} XP\n"
            f"**♻️ 重複交換XP**　{exchange_xp} XP\n"
            "未収集カードは、同じレアリティ内で **2倍** 出やすくなります。\n"
            "最初の1枚は必ず棚に残り、**2枚目以降だけ**交換できます。\n"
            "抽選結果はカフェ台帳に公開されます。\n\n"
            "詳しい排出率・カード解説・セットメニューは、下のWeb図鑑で確認できます。"
        ),
        color=DEFAULT_EMBED_COLOR,
    )
    embed.set_image(url="attachment://panel-cabinet.jpg")
    embed.set_footer(text="1日1回の無料分は毎日 0:00に更新")
    return embed


def _metric(
    entry: CafeRankingEntry,
    category: str,
    rankings: CafeRankings,
) -> str:
    if category == "collection":
        total = rankings.category_totals[category]
        percentage = entry.collection_count / total * 100
        return f"**{entry.collection_count}/{total}種**（{percentage:.1f}%）"
    if category == "mastery":
        return (
            f"**{entry.mastery_score:,} pt**（看板 {entry.signature_cards} / "
            f"常連 {entry.regular_cards} / なじみ {entry.familiar_cards}）"
        )
    if category == "sets":
        return (
            f"**{entry.completed_sets}/{rankings.set_count}セット**"
            f"（図鑑 {entry.collection_count}種）"
        )
    if category == "rare":
        return (
            f"**{entry.rare_collection_count}/"
            f"{rankings.category_totals[category]}種**"
            f"（R {entry.rare_r_count} / SR {entry.rare_sr_count} / "
            f"SSR {entry.rare_ssr_count} / UR {entry.rare_ur_count} / "
            f"幻 {entry.rare_mythic_count}）"
        )
    if category == "treasure":
        return (
            f"**{entry.treasure_collection_count}/"
            f"{rankings.category_totals[category]}種**"
            f"（UR {entry.rare_ur_count} / 幻 {entry.rare_mythic_count}）"
        )
    if category == "joke":
        return (
            f"**{entry.n_mastery_score:,} pt**"
            f"（N {entry.n_collection_count}/"
            f"{rankings.category_totals[category]}種・"
            f"看板 {entry.n_signature_cards}）"
        )
    collection_count = getattr(entry, f"{category}_collection_count")
    mastery_score = getattr(entry, f"{category}_mastery_score")
    signature_cards = getattr(entry, f"{category}_signature_cards")
    return (
        f"**{mastery_score:,} pt**"
        f"（収集 {collection_count}/{rankings.category_totals[category]}種・"
        f"看板 {signature_cards}）"
    )


def _line(entry: CafeRankingEntry, category: str, rankings: CafeRankings) -> str:
    prefix = {1: "🥇", 2: "🥈", 3: "🥉"}.get(entry.rank, f"**#{entry.rank}**")
    return f"{prefix} <@{entry.user_id}> — {_metric(entry, category, rankings)}"


def _category(rankings: CafeRankings, key: str) -> CafeRankingCategory | None:
    return next(
        (category for category in rankings.categories if category.key == key), None
    )


def build_ranking_panel_embed(rankings: CafeRankings) -> discord.Embed:
    embed = discord.Embed(
        title=RANKING_TITLE,
        description=(
            "全10部門のTOP 3を常に表示しています。\n"
            "各ボタンではTOP 20と自分の順位、Web版では全10部門をまとめて確認できます。"
        ),
        color=DEFAULT_EMBED_COLOR,
    )
    for key, presentation in CATEGORY_PRESENTATIONS.items():
        category = _category(rankings, key)
        lines = (
            [_line(entry, key, rankings) for entry in category.entries[:3]]
            if category is not None
            else []
        )
        embed.add_field(
            name=f"{presentation.emoji} {presentation.button_label} TOP 3",
            value=(
                "\n".join(lines)
                if lines
                else "UR・幻の収集記録はまだありません。"
                if key == "treasure"
                else "まだ抽選記録がありません。"
            ),
            inline=False,
        )
    updated = rankings.captured_at.astimezone(TOKYO).strftime("%m/%d %H:%M")
    embed.set_footer(
        text=(
            f"ボタン操作時に更新 · 集計は最大5分間キャッシュ · 最終集計 {updated} JST"
        )
    )
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
    empty_message = (
        "UR・幻の収集記録はまだありません。"
        if category_key == "treasure"
        else "まだ抽選記録がありません。"
    )
    lines = [_line(entry, category_key, rankings) for entry in entries]
    embed = discord.Embed(
        title=f"{presentation.emoji} {presentation.title}",
        description=(
            f"{presentation.explanation}\n\n"
            + ("\n".join(lines) if lines else empty_message)
        ),
        color=DEFAULT_EMBED_COLOR,
    )
    viewer = (
        category.viewer_entry
        if (
            category is not None
            and category.viewer_entry is not None
            and category.viewer_entry.user_id == viewer_id
        )
        else next((entry for entry in entries if entry.user_id == viewer_id), None)
    )
    embed.add_field(
        name="あなたの順位",
        value=(
            _line(viewer, category_key, rankings)
            if viewer is not None
            else empty_message
        ),
        inline=False,
    )
    updated = rankings.captured_at.astimezone(TOKYO).strftime("%m/%d %H:%M")
    embed.set_footer(
        text=(
            f"{presentation.tiebreaker} · ボタン操作時に更新 · "
            "集計は最大5分間キャッシュ · "
            f"最終集計 {updated} JST"
        )
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
        color=DEFAULT_EMBED_COLOR,
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
