from datetime import UTC, datetime
from typing import cast

import discord

from cafe_collection.cog import CafePanelView, CafeRankingView
from cafe_collection.level_api import (
    CafeCapabilities,
    CafeRankingCategory,
    CafeRankingEntry,
    CafeRankings,
)
from cafe_collection.presentation import (
    build_panel_embed,
    build_ranking_detail_embed,
    build_ranking_panel_embed,
)


def _capabilities() -> CafeCapabilities:
    return CafeCapabilities(
        api_version=4,
        catalog_size=373,
        asset_count=375,
        asset_manifest_sha256="test",
        paid_draw_cost_xp=20,
        hourly_draw_limit=10,
        minimum_draw_reward_xp=25,
        maximum_draw_reward_xp=5000,
        draw_reward_xp_by_rarity={
            "C": 25,
            "UC": 30,
            "R": 60,
            "SR": 150,
            "SSR": 500,
            "UR": 1500,
            "MYTHIC": 5000,
        },
        exchange_xp_by_rarity={
            "C": 5,
            "UC": 10,
            "R": 20,
            "SR": 50,
            "SSR": 150,
            "UR": 500,
            "MYTHIC": 1500,
        },
        ranking_category_totals={},
        set_count=50,
    )


def _ranking_entry() -> CafeRankingEntry:
    return CafeRankingEntry(
        rank=1,
        user_id="2001",
        collection_count=21,
        mastery_score=21,
        familiar_cards=0,
        regular_cards=0,
        signature_cards=0,
        completed_sets=0,
        rare_collection_count=0,
        rare_r_count=0,
        rare_sr_count=0,
        rare_ssr_count=0,
        rare_ur_count=0,
        rare_mythic_count=0,
        treasure_collection_count=0,
        n_collection_count=21,
        n_mastery_score=21,
        n_signature_cards=0,
        coffee_collection_count=0,
        coffee_mastery_score=0,
        coffee_signature_cards=0,
        tea_collection_count=0,
        tea_mastery_score=0,
        tea_signature_cards=0,
        sweets_collection_count=0,
        sweets_mastery_score=0,
        sweets_signature_cards=0,
        culture_collection_count=0,
        culture_mastery_score=0,
        culture_signature_cards=0,
    )


def _rankings() -> CafeRankings:
    keys = (
        "collection",
        "mastery",
        "sets",
        "rare",
        "treasure",
        "joke",
        "coffee",
        "tea",
        "sweets",
        "culture",
    )
    return CafeRankings(
        participant_count=1,
        total_draws=21,
        captured_at=datetime(2026, 8, 17, 9, 30, tzinfo=UTC),
        category_totals=dict.fromkeys(keys, 373),
        set_count=50,
        categories=[
            CafeRankingCategory(
                key=key,
                entries=[_ranking_entry()] if key == "collection" else [],
                viewer_entry=_ranking_entry() if key == "collection" else None,
            )
            for key in keys
        ],
    )


def test_panel_text_is_word_for_word_identical_to_existing_bot() -> None:
    embed = build_panel_embed(_capabilities())

    assert embed.title == "☕ カフェ・コレクション"
    assert embed.description == (
        "カードを集めながら、**引くたびXPが必ず増える**コレクションです。\n\n"
        "**🎟️ 1日1回無料** / 2回目以降 20 XP / "
        "1時間10回まで / **1日の合計上限なし**\n"
        "**必ず黒字：25〜5000 XP獲得**（有料でも +5 XP以上）\n\n"
        "**✨ 抽選の獲得XP**　N 25 / HN 30 / R 60 / SR 150 / SSR 500 / "
        "UR 1500 / 幻 5000 XP\n"
        "**♻️ 重複交換XP**　N 5 / HN 10 / R 20 / SR 50 / SSR 150 / "
        "UR 500 / 幻 1500 XP\n"
        "未収集カードは、同じレアリティ内で **2倍** 出やすくなります。\n"
        "最初の1枚は必ず棚に残り、**2枚目以降だけ**交換できます。\n"
        "抽選結果はカフェ台帳に公開されます。\n\n"
        "詳しい排出率・カード解説・セットメニューは、下のWeb図鑑で確認できます。"
    )
    assert embed.color is not None
    assert embed.color.value == 0x5865F2
    assert embed.image.url == "attachment://panel-cabinet.jpg"
    assert embed.footer.text == "1日1回の無料分は毎日 0:00に更新"


async def test_panel_components_match_existing_bot_in_order_and_appearance() -> None:
    view = CafePanelView(guild_id=123456)
    buttons = [
        cast(
            discord.ui.Button[discord.ui.View],
            child.item if isinstance(child, discord.ui.DynamicItem) else child,
        )
        for child in view.children
    ]

    assert [button.label for button in buttons] == [
        "一枚引く",
        "まとめて引く（最大10枚）",
        "自分の棚・重複交換",
        "自分のXP・残り枠",
        "Web図鑑・排出率",
    ]
    assert [
        str(button.emoji) if button.emoji is not None else None for button in buttons
    ] == [
        "☕",
        "🎟️",
        None,
        None,
        "📖",
    ]
    assert [button.style for button in buttons] == [
        discord.ButtonStyle.primary,
        discord.ButtonStyle.success,
        discord.ButtonStyle.secondary,
        discord.ButtonStyle.secondary,
        discord.ButtonStyle.link,
    ]
    assert [button.row for button in buttons] == [0, 0, 1, 1, 1]
    assert buttons[-1].url == "https://chill-cafe.site/cafe-collection/"


def test_ranking_panel_and_detail_match_existing_bot_presentation() -> None:
    rankings = _rankings()
    panel = build_ranking_panel_embed(rankings)
    detail = build_ranking_detail_embed(
        rankings,
        category_key="collection",
        viewer_id="2001",
    )

    assert panel.title == "☕ カフェ・コレクションランキング"
    assert panel.description == (
        "全10部門のTOP 3を常に表示しています。\n"
        "各ボタンではTOP 20と自分の順位、Web版では全10部門をまとめて確認できます。"
    )
    assert [field.name for field in panel.fields] == [
        "📚 図鑑 TOP 3",
        "☕ 熟練度 TOP 3",
        "🍽️ セット TOP 3",
        "💎 レア棚 TOP 3",
        "🏛️ 秘宝棚 TOP 3",
        "🥖 ネタ棚 TOP 3",
        "🫘 珈琲通 TOP 3",
        "🍵 茶の達人 TOP 3",
        "🍰 甘味通 TOP 3",
        "🏺 食文化探訪 TOP 3",
    ]
    assert panel.fields[0].value == "🥇 <@2001> — **21/373種**（5.6%）"
    assert panel.fields[4].value == "UR・幻の収集記録はまだありません。"
    assert panel.footer.text == (
        "ボタン操作時に更新 · 集計は最大5分間キャッシュ · 最終集計 08/17 18:30 JST"
    )
    assert detail.title == "📚 図鑑ランキング"
    assert detail.description == (
        "異なるカードの収集種類数を競います。\n\n🥇 <@2001> — **21/373種**（5.6%）"
    )
    assert detail.fields[0].name == "あなたの順位"
    assert detail.fields[0].value == "🥇 <@2001> — **21/373種**（5.6%）"


def test_ranking_detail_ignores_another_users_viewer_entry() -> None:
    rankings = _rankings()
    collection = rankings.categories[0]
    collection.viewer_entry = _ranking_entry().model_copy(update={"user_id": "9999"})

    detail = build_ranking_detail_embed(
        rankings,
        category_key="collection",
        viewer_id="2001",
    )

    assert detail.fields[0].value == "🥇 <@2001> — **21/373種**（5.6%）"


async def test_ranking_components_match_existing_bot_in_order_and_appearance() -> None:
    view = CafeRankingView(guild_id=123456)
    buttons = [
        cast(
            discord.ui.Button[discord.ui.View],
            child.item if isinstance(child, discord.ui.DynamicItem) else child,
        )
        for child in view.children
    ]

    assert [button.label for button in buttons] == [
        "図鑑",
        "熟練度",
        "セット",
        "レア棚",
        "秘宝棚",
        "ネタ棚",
        "珈琲通",
        "茶の達人",
        "甘味通",
        "食文化探訪",
        "全ランキングをWebで見る",
    ]
    assert [button.row for button in buttons] == [0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 2]
    assert buttons[-1].url == "https://chill-cafe.site/cafe-collection/rankings/"
