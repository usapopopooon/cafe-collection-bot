import json
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, Mock

import discord
import httpx
import pytest
from discord import app_commands
from discord.ext import commands

from cafe_collection import cog as cog_module
from cafe_collection import collection_ui as collection_ui_module
from cafe_collection.cog import (
    CafeCog,
    CafePanelCollectionButton,
    CafePanelDrawButton,
    CafePanelView,
    DrawConfirmView,
    _draw,
    _send_draw_result,
)
from cafe_collection.collection_ui import (
    DISCORD_EMBED_DESCRIPTION_LIMIT,
    DISCORD_EMBED_FIELD_NAME_LIMIT,
    DISCORD_EMBED_FIELD_VALUE_LIMIT,
    DISCORD_EMBED_FOOTER_LIMIT,
    DISCORD_EMBED_TITLE_LIMIT,
    DISCORD_EMBED_TOTAL_LIMIT,
    EMBED_DESCRIPTION_BUDGET,
    EMBED_TOTAL_BUDGET,
    CardChoiceView,
    CollectionActionsView,
    CustomQuantityModal,
    RarityBulkExchangeView,
    RarityPageView,
    RedemptionConfirmView,
    ShelfPageView,
    _collection_summary,
    show_full_collection,
)
from cafe_collection.discord_context import actor_from_interaction as _actor
from cafe_collection.level_api import (
    CafeActor,
    CafeApiClient,
    CafeApiError,
    CafeAvailability,
    CafeCapabilities,
    CafeCollection,
    CafeCollectionCard,
    CafeCosmetic,
    CafeDraw,
    CafeDrawBatch,
    CafeMasterySummary,
    CafeRankingCategory,
    CafeRankingEntry,
    CafeRankings,
    CafeWallet,
)


def _interaction(
    *,
    interaction_id: int,
    guild_id: int = 1001,
    user_id: int = 11,
    role_ids: tuple[int, ...] = (9001,),
    display_name: str = "カフェ客",
    manage_guild: bool = False,
) -> discord.Interaction:
    guild = Mock(spec=discord.Guild)
    guild.id = guild_id
    guild.me = None
    roles = []
    for role_id in role_ids:
        role = Mock(spec=discord.Role)
        role.id = role_id
        roles.append(role)
    member = Mock(spec=discord.Member)
    member.id = user_id
    member.roles = roles
    member.display_name = display_name
    permissions = Mock(spec=discord.Permissions)
    permissions.administrator = False
    permissions.manage_guild = manage_guild
    response = Mock(spec=discord.InteractionResponse)
    response.defer = AsyncMock()
    response.send_message = AsyncMock()
    response.edit_message = AsyncMock()
    followup = Mock(spec=discord.Webhook)
    followup.send = AsyncMock()
    interaction = Mock(spec=discord.Interaction)
    interaction.id = interaction_id
    interaction.guild = guild
    interaction.guild_id = guild_id
    interaction.user = member
    interaction.permissions = permissions
    interaction.response = response
    interaction.followup = followup
    interaction.channel = None
    interaction.client = SimpleNamespace(user=None, cafe_api=None)
    return cast(discord.Interaction, interaction)


def _wallet(available_xp: int = 100) -> CafeWallet:
    return CafeWallet(
        total_xp=available_xp,
        spent_xp=0,
        available_xp=available_xp,
    )


def _capabilities() -> CafeCapabilities:
    return CafeCapabilities(
        api_version=4,
        catalog_size=493,
        asset_count=495,
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
        set_count=53,
    )


def _bot() -> commands.Bot:
    return cast(commands.Bot, SimpleNamespace(user=None, guilds=[]))


def _drawn_result() -> CafeDrawBatch:
    wallet = _wallet()
    return CafeDrawBatch(
        status="drawn",
        draws=[],
        wallet_before=wallet,
        wallet_after=wallet,
    )


async def test_ready_repairs_the_configured_ranking_panel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ranking_channel = Mock(spec=discord.TextChannel)
    ranking_channel.id = 3003
    guild = Mock(spec=discord.Guild)
    guild.id = 1001
    guild.get_channel.return_value = ranking_channel
    bot_user = SimpleNamespace(id=99)
    bot = cast(commands.Bot, SimpleNamespace(user=bot_user, guilds=[guild]))
    api = Mock(spec=CafeApiClient)
    api.layout = AsyncMock(
        return_value=SimpleNamespace(ranking_channel_id=str(ranking_channel.id))
    )
    cog = CafeCog(bot, cast(CafeApiClient, api))
    ensure_setup = AsyncMock(return_value=None)
    upsert_ranking = AsyncMock()
    publish_pending = AsyncMock()
    monkeypatch.setattr(cog, "_ensure_setup", ensure_setup)
    monkeypatch.setattr(cog, "_upsert_ranking", upsert_ranking)
    monkeypatch.setattr(
        "cafe_collection.cog.publish_pending_for_guild",
        publish_pending,
    )

    await cog.on_ready()

    actor = CafeActor(
        guild_id="1001",
        user_id="99",
        role_ids=[],
        can_manage_guild=True,
    )
    ensure_setup.assert_awaited_once_with(
        actor=actor,
        guild=guild,
        require_existing=True,
    )
    api.layout.assert_awaited_once_with(actor)
    upsert_ranking.assert_awaited_once_with(
        actor=actor,
        guild=guild,
        channel=ranking_channel,
    )
    publish_pending.assert_awaited_once_with(bot, api, guild)


async def test_ban_immediately_clears_cache_and_refreshes_the_ranking_panel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cog_module, "_ranking_cache", {1001: (Mock(), 1.0)})
    monkeypatch.setattr(
        cog_module,
        "_ranking_viewer_cache",
        {(1001, "11"): (Mock(), 1.0)},
    )
    monkeypatch.setattr(cog_module, "_ranking_banned_user_ids", {})
    ranking_channel = Mock(spec=discord.TextChannel)
    ranking_channel.id = 3003
    guild = Mock(spec=discord.Guild)
    guild.id = 1001
    guild.get_channel.return_value = ranking_channel
    user = Mock(spec=discord.User)
    user.id = 11
    bot_user = SimpleNamespace(id=99)
    bot = cast(commands.Bot, SimpleNamespace(user=bot_user, guilds=[guild]))
    api = Mock(spec=CafeApiClient)
    api.layout = AsyncMock(
        return_value=SimpleNamespace(ranking_channel_id=str(ranking_channel.id))
    )
    cog = CafeCog(bot, cast(CafeApiClient, api))
    upsert_ranking = AsyncMock()
    monkeypatch.setattr(cog, "_upsert_ranking", upsert_ranking)

    await cog.on_member_ban(guild, user)

    assert cog_module._ranking_cache == {}
    assert cog_module._ranking_viewer_cache == {}
    assert cog_module._ranking_banned_user_ids == {1001: {"11"}}
    upsert_ranking.assert_awaited_once_with(
        actor=CafeActor(
            guild_id="1001",
            user_id="99",
            role_ids=[],
            can_manage_guild=True,
        ),
        guild=guild,
        channel=ranking_channel,
    )


async def test_periodic_refresh_is_the_fallback_when_ban_events_are_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cog_module, "_ranking_cache", {1001: (Mock(), 1.0)})
    monkeypatch.setattr(
        cog_module,
        "_ranking_viewer_cache",
        {(1001, "11"): (Mock(), 1.0)},
    )
    guild = Mock(spec=discord.Guild)
    guild.id = 1001
    bot = cast(
        commands.Bot,
        SimpleNamespace(user=SimpleNamespace(id=99), guilds=[guild]),
    )
    cog = CafeCog(bot, cast(CafeApiClient, Mock(spec=CafeApiClient)))
    refresh = AsyncMock()
    monkeypatch.setattr(cog, "_refresh_configured_ranking", refresh)

    await cast(Any, CafeCog.ranking_refresh_loop).coro(cog)

    assert cog_module._ranking_cache == {}
    assert cog_module._ranking_viewer_cache == {}
    refresh.assert_awaited_once_with(guild)


async def test_draw_result_only_points_to_ledger_without_showing_the_card() -> None:
    interaction = _interaction(interaction_id=5000)
    result = CafeDrawBatch(
        status="drawn",
        draws=[
            CafeDraw(
                event_id="5000:0",
                batch_position=0,
                reward_key="spent-tea",
                reward_name="出がらし",
                reward_description="説明",
                rarity="C",
                image_filename="spent-tea.jpg",
                draw_type="free",
                cost_xp=0,
                reward_xp=25,
                exchange_xp=5,
                was_duplicate=False,
                owned_count=1,
                collected_count=1,
            )
        ],
        wallet_before=_wallet(100),
        wallet_after=_wallet(125),
    )

    await _send_draw_result(
        interaction,
        result,
        count=1,
        ledger_published=True,
    )

    send = cast(AsyncMock, interaction.followup.send)
    send.assert_awaited_once_with(
        "抽選が完了しました。**カフェ台帳**で結果を確認してください。\n"
        "現在XP: **125 XP**",
        ephemeral=True,
    )


async def test_free_draw_wires_current_discord_actor_and_request_fields() -> None:
    interaction = _interaction(interaction_id=5001, manage_guild=True)
    actor = CafeActor(
        guild_id="1001",
        user_id="11",
        role_ids=["9001"],
        can_manage_guild=True,
    )
    assert _actor(interaction) == actor
    api = Mock(spec=CafeApiClient)
    api.authorize = AsyncMock()
    api.availability = AsyncMock(
        return_value=CafeAvailability(
            wallet=_wallet(),
            has_free_draw=True,
            hourly_remaining=10,
            requested_count=2,
            cost_xp=0,
        )
    )
    api.draw = AsyncMock(return_value=_drawn_result())
    api.capabilities = AsyncMock(return_value=_capabilities())
    await _draw(interaction, api=cast(CafeApiClient, api), count=1)

    api.availability.assert_awaited_once_with(actor, count=1)
    api.draw.assert_awaited_once_with(
        actor,
        event_id="5001",
        display_name="カフェ客",
        count=1,
        expected_cost_xp=0,
    )


async def test_paid_confirmation_reloads_member_roles_before_drawing() -> None:
    initial_interaction = _interaction(interaction_id=5002, role_ids=(9001,))
    initial_actor = CafeActor(
        guild_id="1001",
        user_id="11",
        role_ids=["9001"],
        can_manage_guild=False,
    )
    api = Mock(spec=CafeApiClient)
    api.authorize = AsyncMock()
    api.availability = AsyncMock(
        return_value=CafeAvailability(
            wallet=_wallet(),
            has_free_draw=False,
            hourly_remaining=10,
            requested_count=1,
            cost_xp=20,
        )
    )
    api.draw = AsyncMock(return_value=_drawn_result())
    api.capabilities = AsyncMock(return_value=_capabilities())
    await _draw(initial_interaction, api=cast(CafeApiClient, api), count=1)

    api.availability.assert_awaited_once_with(initial_actor, count=1)
    api.draw.assert_not_awaited()
    send = cast(AsyncMock, initial_interaction.followup.send)
    assert send.await_args is not None
    view = send.await_args.kwargs["view"]
    assert isinstance(view, DrawConfirmView)
    assert send.await_args.args[0] == (
        "**1枚を引きます**。\n"
        "現在XP: **100 XP**\n"
        "消費: **20 XP**\n"
        "最低獲得: **25 XP**\n"
        "抽選後: **105 XP以上**\n"
        "この時間の残り枠: 10 → **9回**"
    )

    confirm_interaction = _interaction(
        interaction_id=5003,
        role_ids=(9002,),
        manage_guild=True,
    )
    button = cast(discord.ui.Button[DrawConfirmView], view.children[0])
    await button.callback(confirm_interaction)

    api.draw.assert_awaited_once_with(
        CafeActor(
            guild_id="1001",
            user_id="11",
            role_ids=["9002"],
            can_manage_guild=True,
        ),
        event_id=view.event_id,
        display_name="カフェ客",
        count=1,
        expected_cost_xp=20,
    )


async def test_full_collection_shows_actions_before_rendering_shelf_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    interaction = _interaction(interaction_id=5004)
    actor = CafeActor(
        guild_id="1001",
        user_id="11",
        role_ids=["9001"],
        can_manage_guild=False,
    )
    selected_card = CafeCollectionCard(
        key="spent-tea",
        name="出がらしティー",
        rarity="C",
        description="説明",
        image_filename="spent-tea.jpg",
        count=1,
        redeemable_count=0,
        lifetime_count=1,
        is_protected=False,
    )
    other_card = CafeCollectionCard(
        key="americano",
        name="アメリカーノ",
        rarity="R",
        description="説明",
        image_filename="americano.jpg",
        count=1,
        redeemable_count=0,
        lifetime_count=1,
        is_protected=False,
    )
    api = Mock(spec=CafeApiClient)
    api.authorize = AsyncMock()
    api.collection = AsyncMock(
        return_value=CafeCollection(
            cards=[selected_card, other_card],
            endgame_pity_active=False,
            endgame_pity_duplicate_draws=100,
            mastery_tiers=[
                CafeMasterySummary(name="発見", emoji="🔎", card_count=2),
                CafeMasterySummary(name="なじみ", emoji="☕", card_count=0),
                CafeMasterySummary(name="常連", emoji="⭐", card_count=0),
                CafeMasterySummary(name="看板メニュー", emoji="🏆", card_count=0),
            ],
        )
    )
    rendered_cards: list[list[CafeCollectionCard]] = []

    def render(cards: list[CafeCollectionCard], page: int) -> bytes:
        assert page == 0
        rendered_cards.append(cards)
        return b"\xff\xd8\xff\xd9"

    monkeypatch.setattr(collection_ui_module, "render_collection_page", render)
    await show_full_collection(interaction, api=cast(CafeApiClient, api))

    api.collection.assert_awaited_once_with(actor)
    assert rendered_cards == [[selected_card]]
    send = cast(AsyncMock, interaction.followup.send)
    assert send.await_count == 2
    assert isinstance(send.await_args_list[0].kwargs["view"], CollectionActionsView)
    shelf = send.await_args_list[1].kwargs["view"]
    assert isinstance(shelf, ShelfPageView)
    assert {option.value for option in cast(Any, shelf.children[-1]).options} == {
        "C",
        "R",
    }

    next_interaction = _interaction(interaction_id=5008)
    cast(Any, next_interaction).edit_original_response = AsyncMock()
    await shelf.show_page(next_interaction, rarity="R", page=0)

    assert rendered_cards == [[selected_card], [other_card]]
    cast(AsyncMock, next_interaction.edit_original_response).assert_awaited_once()


async def test_full_collection_keeps_large_shelf_embeds_within_discord_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    interaction = _interaction(interaction_id=5007)
    cards = [
        CafeCollectionCard(
            key=f"large-shelf-{index}",
            name=f"とても長い名前のカフェカードその{index:03d}",
            rarity="C",
            description="説明",
            image_filename=f"large-shelf-{index}.jpg",
            count=3,
            redeemable_count=2,
            lifetime_count=3,
            is_protected=True,
            mastery_name="なじみ",
            mastery_emoji="☕",
        )
        for index in range(250)
    ]
    collection = CafeCollection(
        cards=cards,
        endgame_pity_active=False,
        endgame_pity_duplicate_draws=100,
        mastery_tiers=[],
    )
    api = Mock(spec=CafeApiClient)
    api.authorize = AsyncMock()
    api.collection = AsyncMock(return_value=collection)

    monkeypatch.setattr(
        collection_ui_module,
        "render_collection_page",
        lambda _rendered_cards, _page: b"\xff\xd8\xff\xd9",
    )

    await show_full_collection(interaction, api=cast(CafeApiClient, api))

    send = cast(AsyncMock, interaction.followup.send)
    assert send.await_count == 2
    sent_embeds = [call.kwargs["embed"] for call in send.await_args_list]
    assert sent_embeds[0].description is not None
    assert "棚画像で確認できます" in sent_embeds[0].description
    for embed in sent_embeds:
        assert len(embed.title or "") <= DISCORD_EMBED_TITLE_LIMIT
        assert len(embed.description or "") <= DISCORD_EMBED_DESCRIPTION_LIMIT
        assert len(embed.footer.text or "") <= DISCORD_EMBED_FOOTER_LIMIT
        assert len(embed) <= DISCORD_EMBED_TOTAL_LIMIT
        assert len(embed.description or "") <= EMBED_DESCRIPTION_BUDGET
        assert len(embed) <= EMBED_TOTAL_BUDGET
        assert all(
            len(field.name) <= DISCORD_EMBED_FIELD_NAME_LIMIT
            and len(field.value) <= DISCORD_EMBED_FIELD_VALUE_LIMIT
            for field in embed.fields
        )


async def test_full_collection_uses_existing_bot_error_message() -> None:
    interaction = _interaction(interaction_id=5005)
    api = Mock(spec=CafeApiClient)
    api.authorize = AsyncMock()
    api.collection = AsyncMock(side_effect=CafeApiError("unavailable"))

    await show_full_collection(interaction, api=cast(CafeApiClient, api))

    send = cast(AsyncMock, interaction.followup.send)
    send.assert_awaited_once_with(
        "カード棚の読み込みに失敗しました。時間をおいてもう一度お試しください。",
        ephemeral=True,
    )


async def test_shelf_image_failure_keeps_exchange_actions_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    card = CafeCollectionCard(
        key="spent-tea",
        name="出がらしティー",
        rarity="C",
        description="説明",
        image_filename="spent-tea.jpg",
        count=2,
        redeemable_count=1,
        lifetime_count=2,
        is_protected=False,
        exchangeable_count=1,
        exchange_xp=5,
        exchange_medals=1,
    )
    api = Mock(spec=CafeApiClient)
    api.authorize = AsyncMock()
    api.collection = AsyncMock(
        return_value=CafeCollection(
            cards=[card],
            endgame_pity_active=False,
            endgame_pity_duplicate_draws=100,
            mastery_tiers=[],
        )
    )

    def fail(_cards: list[CafeCollectionCard], _page: int) -> bytes:
        raise ValueError("image unavailable")

    monkeypatch.setattr(collection_ui_module, "render_collection_page", fail)
    interaction = _interaction(interaction_id=5014)

    await show_full_collection(interaction, api=cast(CafeApiClient, api))

    send = cast(AsyncMock, interaction.followup.send)
    assert send.await_count == 2
    actions = send.await_args_list[0].kwargs["view"]
    assert isinstance(actions, CollectionActionsView)
    assert any(
        getattr(item, "label", None) == "重複を選んでXP交換"
        for item in actions.children
    )
    assert "棚画像を表示できませんでした" in send.await_args_list[1].args[0]


async def test_collection_button_reports_unexpected_loading_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    interaction = _interaction(interaction_id=5006)
    cast(Any, interaction.client).cafe_api = Mock(spec=CafeApiClient)
    is_done = cast(Mock, interaction.response.is_done)
    is_done.return_value = True
    monkeypatch.setattr(
        cog_module,
        "show_full_collection",
        AsyncMock(side_effect=ValueError("too many embeds")),
    )

    await CafePanelCollectionButton(guild_id=1001).callback(interaction)

    send = cast(AsyncMock, interaction.followup.send)
    send.assert_awaited_once_with(
        "カード棚の読み込みに失敗しました。時間をおいてもう一度お試しください。",
        ephemeral=True,
    )


async def test_ranking_cache_keeps_viewer_entries_separate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cog_module, "_ranking_cache", {})
    monkeypatch.setattr(cog_module, "_ranking_viewer_cache", {})
    monkeypatch.setattr(cog_module, "_ranking_locks", {})
    rankings_by_user = {
        user_id: cast(CafeRankings, SimpleNamespace(viewer_id=user_id))
        for user_id in ("99", "11", "12")
    }
    api = Mock(spec=CafeApiClient)
    api.rankings = AsyncMock(side_effect=lambda actor: rankings_by_user[actor.user_id])

    def actor(user_id: str) -> CafeActor:
        return CafeActor(
            guild_id="1001",
            user_id=user_id,
            role_ids=[],
            can_manage_guild=user_id == "99",
        )

    bot_result = await cog_module._get_cached_rankings(api, actor("99"))
    first_result = await cog_module._get_cached_rankings(api, actor("11"))
    second_result = await cog_module._get_cached_rankings(api, actor("12"))
    repeated_result = await cog_module._get_cached_rankings(api, actor("11"))

    assert bot_result == (rankings_by_user["99"], True)
    assert first_result == (rankings_by_user["11"], False)
    assert second_result == (rankings_by_user["12"], False)
    assert repeated_result == (rankings_by_user["11"], False)
    assert api.rankings.await_count == 3


def test_known_bans_are_removed_from_cached_ranking_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blocked = CafeRankingEntry.model_construct(user_id="11")
    visible = CafeRankingEntry.model_construct(user_id="12")
    rankings = CafeRankings.model_construct(
        categories=[
            CafeRankingCategory.model_construct(
                key="collection",
                entries=[blocked, visible],
                viewer_entry=blocked,
            )
        ]
    )
    monkeypatch.setattr(
        cog_module,
        "_ranking_banned_user_ids",
        {1001: {"11"}},
    )

    filtered = cog_module._without_known_bans(rankings, 1001)

    assert [entry.user_id for entry in filtered.categories[0].entries] == ["12"]
    assert filtered.categories[0].viewer_entry is None


async def test_stale_configured_channel_creates_a_bot_owned_replacement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    default_role = Mock(spec=discord.Role)
    named_channel = Mock(spec=discord.TextChannel)
    created_channel = Mock(spec=discord.TextChannel)
    created_channel.overwrites_for = Mock(return_value=discord.PermissionOverwrite())
    created_channel.set_permissions = AsyncMock()
    guild = Mock(spec=discord.Guild)
    guild.default_role = default_role
    guild.me = None
    guild.text_channels = [named_channel]
    guild.get_channel = Mock(return_value=None)
    guild.create_text_channel = AsyncMock(return_value=created_channel)
    name_lookup = Mock(return_value=named_channel)
    monkeypatch.setattr(discord.utils, "get", name_lookup)

    result = await cog_module._find_or_create_channel(
        cast(discord.Guild, guild),
        "📒カフェ台帳",
        "3002",
    )

    assert result is created_channel
    name_lookup.assert_not_called()
    guild.create_text_channel.assert_awaited_once()


async def test_panel_draw_uses_distinct_component_id_and_interaction_id() -> None:
    requests: list[tuple[str, dict[str, Any]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = cast(dict[str, Any], json.loads(request.content))
        requests.append((request.url.path, payload))
        if request.url.path.endswith("/draw-availability"):
            return httpx.Response(
                200,
                json={
                    "wallet": {
                        "total_xp": 100,
                        "spent_xp": 0,
                        "available_xp": 100,
                    },
                    "has_free_draw": True,
                    "hourly_remaining": 10,
                    "requested_count": 1,
                    "cost_xp": 0,
                },
            )
        return httpx.Response(
            200,
            json={
                "status": "drawn",
                "draws": [],
                "wallet_before": {
                    "total_xp": 100,
                    "spent_xp": 0,
                    "available_xp": 100,
                },
                "wallet_after": {
                    "total_xp": 100,
                    "spent_xp": 0,
                    "available_xp": 100,
                },
            },
        )

    api = CafeApiClient(
        "https://level.example.com",
        "cafe-secret",
        transport=httpx.MockTransport(handler),
    )
    interaction = _interaction(interaction_id=7001)
    cast(Any, interaction).client = SimpleNamespace(user=None, cafe_api=api)
    button = CafePanelDrawButton(count=1, guild_id=1001)
    try:
        await button.callback(interaction)
    finally:
        await api.close()

    assert button.item.custom_id == "cafe-collection:draw:1:1001"
    assert all(
        item.item.custom_id.startswith("cafe-collection:")
        for item in CafePanelView(guild_id=1001).children
        if isinstance(item, discord.ui.DynamicItem)
    )
    assert {
        getattr(item.item, "label", None)
        for item in CafePanelView(guild_id=1001).children
        if isinstance(item, discord.ui.DynamicItem)
    } == {
        "一枚引く",
        "まとめて引く（最大10枚）",
        "自分の棚・重複交換",
        "自分のXP・残り枠",
    }
    draw_request = next(
        payload for path, payload in requests if path.endswith("/draws")
    )
    assert draw_request["event_id"] == "7001"


def test_cafe_command_group_exposes_user_and_admin_feature_parity() -> None:
    assert {command.name for command in CafeCog.__cog_app_commands__} == {
        "cafe-collection"
    }
    cafe_collection = next(
        command
        for command in CafeCog.__cog_app_commands__
        if command.name == "cafe-collection"
    )
    assert isinstance(cafe_collection, app_commands.Group)
    assert {command.name for command in cafe_collection.commands} == {
        "setup",
        "leaderboard-panel",
        "stats",
        "access-role",
        "protect",
    }
    assert [command.name for command in cafe_collection.commands] == [
        "access-role",
        "setup",
        "leaderboard-panel",
        "stats",
        "protect",
    ]
    assert {
        command.name: command.description for command in cafe_collection.commands
    } == {
        "setup": "カウンター・台帳・抽選パネルを作成または修復",
        "leaderboard-panel": "選んだチャンネルへランキングパネルを投稿または更新",
        "stats": "利用状況とXP収支を管理者だけに表示",
        "access-role": "カフェ・コレクションの利用ロール管理",
        "protect": "名前検索で所持カードの保護／解除を切り替える",
    }
    access_role = next(
        command for command in cafe_collection.commands if command.name == "access-role"
    )
    assert isinstance(access_role, app_commands.Group)
    assert {command.name for command in access_role.commands} == {
        "add",
        "remove",
        "list",
    }
    assert {command.name: command.description for command in access_role.commands} == {
        "add": "利用できるロールを追加",
        "remove": "利用ロールを削除",
        "list": "利用ロールを表示",
    }
    commands_by_name = {command.name: command for command in cafe_collection.commands}
    stats_command = commands_by_name["stats"]
    setup_command = commands_by_name["setup"]
    leaderboard_command = commands_by_name["leaderboard-panel"]
    protect_command = commands_by_name["protect"]
    assert isinstance(stats_command, app_commands.Command)
    assert isinstance(setup_command, app_commands.Command)
    assert isinstance(leaderboard_command, app_commands.Command)
    assert isinstance(protect_command, app_commands.Command)
    assert len(stats_command.checks) == 1
    assert len(setup_command.checks) == 2
    assert len(leaderboard_command.checks) == 1
    assert all(
        isinstance(command, app_commands.Command) and len(command.checks) == 1
        for command in access_role.commands
    )
    assert len(protect_command.checks) == 0
    assert cafe_collection.description == "カフェ・コレクションの管理"


async def test_legacy_ledger_header_is_deleted_instead_of_reposted() -> None:
    bot_user = SimpleNamespace(id=4001)
    bot = cast(commands.Bot, SimpleNamespace(user=bot_user, guilds=[]))
    api = Mock(spec=CafeApiClient)
    cog = CafeCog(bot, cast(CafeApiClient, api))
    message = Mock(spec=discord.Message)
    message.author = bot_user
    message.embeds = [discord.Embed(title="📒 カフェ台帳")]
    message.delete = AsyncMock()
    channel = Mock(spec=discord.TextChannel)
    channel.fetch_message = AsyncMock(return_value=message)

    await cog._delete_legacy_ledger_header(
        channel=cast(discord.TextChannel, channel),
        message_id="3001",
    )

    message.delete.assert_awaited_once_with()


async def test_legacy_ledger_header_is_found_and_deleted_without_saved_id() -> None:
    bot_user = SimpleNamespace(id=4001)
    bot = cast(commands.Bot, SimpleNamespace(user=bot_user, guilds=[]))
    api = Mock(spec=CafeApiClient)
    cog = CafeCog(bot, cast(CafeApiClient, api))
    message = Mock(spec=discord.Message)
    message.author = bot_user
    message.embeds = [discord.Embed(title="📒 カフェ台帳")]
    message.delete = AsyncMock()

    async def history() -> AsyncIterator[discord.Message]:
        yield message

    channel = Mock(spec=discord.TextChannel)
    channel.history = Mock(return_value=history())

    await cog._delete_legacy_ledger_header(
        channel=cast(discord.TextChannel, channel),
        message_id=None,
    )

    message.delete.assert_awaited_once_with()


async def test_maximum_draw_matches_old_panel_affordable_count() -> None:
    interaction = _interaction(interaction_id=8001)
    actor = CafeActor(
        guild_id="1001",
        user_id="11",
        role_ids=["9001"],
        can_manage_guild=False,
    )
    api = Mock(spec=CafeApiClient)
    api.authorize = AsyncMock()
    api.availability = AsyncMock(
        return_value=CafeAvailability(
            wallet=_wallet(20),
            has_free_draw=True,
            hourly_remaining=5,
            requested_count=10,
            cost_xp=180,
        )
    )
    api.capabilities = AsyncMock(return_value=_capabilities())
    api.draw = AsyncMock(return_value=_drawn_result())

    await _draw(
        interaction,
        api=cast(CafeApiClient, api),
        count=10,
        flexible_maximum=True,
    )

    api.draw.assert_not_awaited()
    send = cast(AsyncMock, interaction.followup.send)
    assert send.await_args is not None
    view = send.await_args.kwargs["view"]
    assert isinstance(view, DrawConfirmView)
    assert view.count == 5
    assert view.expected_cost_xp == 80
    assert view.actor == actor
    assert send.await_args.args[0] == (
        "**5枚をまとめて引きます**（本日の無料1枚を含む）。\n"
        "現在XP: **20 XP**\n"
        "消費: **80 XP**\n"
        "最低獲得: **125 XP**\n"
        "抽選後: **65 XP以上**\n"
        "この時間の残り枠: 5 → **0回**\n"
        "獲得XPを次の1枚の費用に充てながら引きます。"
    )


def test_collection_summary_matches_old_bot_details_and_pity_conditions() -> None:
    n_card = CafeCollectionCard(
        key="spent-tea",
        name="出がらしティー",
        rarity="C",
        description="説明",
        image_filename="spent-tea.jpg",
        count=3,
        redeemable_count=2,
        lifetime_count=3,
        is_protected=True,
        exchangeable_count=0,
        mastery_name="なじみ",
        mastery_emoji="☕",
    )
    collection = CafeCollection(
        cards=[n_card],
        duplicate_draw_streak=99,
        endgame_pity_active=False,
        endgame_pity_duplicate_draws=100,
        mastery_tiers=[
            CafeMasterySummary(name="発見", emoji="🔎", card_count=0),
            CafeMasterySummary(name="なじみ", emoji="☕", card_count=1),
            CafeMasterySummary(name="常連", emoji="⭐", card_count=0),
            CafeMasterySummary(name="看板メニュー", emoji="🏆", card_count=0),
        ],
    )

    embed = _collection_summary(collection, display_name="カフェ客")

    assert embed.description is not None
    assert "**N 所持カード**" in embed.description
    assert "**出がらしティー** ×3（🔒重複 2枚を保護）" in embed.description
    assert "☕なじみ（累計3枚）" in embed.description
    mastery = next(field for field in embed.fields if field.name == "☕ カード熟練度")
    assert mastery.value == (
        "🔎発見 0種 / ☕なじみ 1種 / ⭐常連 0種 / 🏆看板メニュー 0種"
    )
    assert all(field.name != "終盤のNEW保証" for field in embed.fields)

    pity_embed = _collection_summary(
        collection.model_copy(update={"endgame_pity_active": True}),
        display_name="カフェ客",
    )
    pity = next(field for field in pity_embed.fields if field.name == "終盤のNEW保証")
    assert pity.value == (
        "NEWなし 99/100回\n上限まで続いた場合、次の抽選は未所持カードになります。"
    )
    assert [field.name for field in pity_embed.fields] == [
        "🪙 カフェメダル",
        "☕ カード熟練度",
        "🏆 N棚の主",
        "終盤のNEW保証",
        "XP交換",
    ]


async def test_collection_actions_keep_existing_and_add_rarity_exchange() -> None:
    card = CafeCollectionCard(
        key="spent-tea",
        name="出がらしティー",
        rarity="C",
        description="説明",
        image_filename="spent-tea.jpg",
        count=2,
        redeemable_count=1,
        lifetime_count=2,
        is_protected=False,
        exchangeable_count=1,
        exchange_xp=10,
        exchange_medals=1,
    )
    collection = CafeCollection(
        cards=[card],
        endgame_pity_active=False,
        endgame_pity_duplicate_draws=100,
        mastery_tiers=[
            CafeMasterySummary(name="発見", emoji="🔎", card_count=0),
            CafeMasterySummary(name="なじみ", emoji="☕", card_count=0),
            CafeMasterySummary(name="常連", emoji="⭐", card_count=0),
            CafeMasterySummary(name="看板メニュー", emoji="🏆", card_count=0),
        ],
        medal_balance=100,
        cosmetics=[
            CafeCosmetic(
                key="sunny-wood",
                name="木漏れ日の棚",
                cost_medals=100,
                color=1,
                decoration="🌿",
            )
        ],
    )

    view = CollectionActionsView(
        guild_id=1001,
        user_id=11,
        collection=collection,
    )

    labels = {getattr(item, "label", None) for item in view.children}
    assert labels == {
        None,
        "カード保護（名前検索）",
        "重複を選んでXP交換",
        "全重複をXP交換",
        "全重複をメダル交換",
        "メダル・棚テーマ",
        "セットメニュー",
        "レアリティ別XP交換",
        "レアリティ別メダル交換",
    }
    rarity_select = view.children[0]
    assert isinstance(rarity_select, discord.ui.Select)
    assert rarity_select.placeholder == "お気に入りするカードのレアリティを選ぶ"
    buttons = [
        cast(discord.ui.Button[discord.ui.View], item) for item in view.children[1:]
    ]
    assert [button.label for button in buttons] == [
        "重複を選んでXP交換",
        "全重複をXP交換",
        "全重複をメダル交換",
        "メダル・棚テーマ",
        "カード保護（名前検索）",
        "セットメニュー",
        "レアリティ別XP交換",
        "レアリティ別メダル交換",
    ]
    assert [button.style for button in buttons] == [
        discord.ButtonStyle.primary,
        discord.ButtonStyle.success,
        discord.ButtonStyle.secondary,
        discord.ButtonStyle.secondary,
        discord.ButtonStyle.secondary,
        discord.ButtonStyle.secondary,
        discord.ButtonStyle.primary,
        discord.ButtonStyle.secondary,
    ]
    assert [button.row for button in buttons] == [1, 1, 2, 2, 3, 3, 4, 4]
    components = view.to_components()
    assert len(components) == 5
    assert all(1 <= len(row["components"]) <= 5 for row in components)


async def test_rarity_exchange_is_hidden_without_exchangeable_duplicates() -> None:
    card = CafeCollectionCard(
        key="protected-tea",
        name="保護したお茶",
        rarity="C",
        description="説明",
        image_filename="protected-tea.jpg",
        count=3,
        redeemable_count=2,
        lifetime_count=3,
        is_protected=True,
        exchangeable_count=0,
    )
    collection = CafeCollection(
        cards=[card],
        endgame_pity_active=False,
        endgame_pity_duplicate_draws=100,
        mastery_tiers=[],
    )

    view = CollectionActionsView(guild_id=1001, user_id=11, collection=collection)

    assert not any("交換" in str(getattr(item, "label", "")) for item in view.children)


async def test_existing_all_duplicate_exchange_still_covers_every_rarity() -> None:
    cards = [
        CafeCollectionCard(
            key=f"{rarity.lower()}-card",
            name=f"{rarity}カード",
            rarity=rarity,
            description="説明",
            image_filename=f"{rarity.lower()}-card.jpg",
            count=exchangeable + 1,
            redeemable_count=exchangeable,
            lifetime_count=exchangeable + 1,
            is_protected=False,
            exchangeable_count=exchangeable,
            exchange_xp=5,
            exchange_medals=1,
        )
        for rarity, exchangeable in (("C", 2), ("R", 3))
    ]
    collection = CafeCollection(
        cards=cards,
        endgame_pity_active=False,
        endgame_pity_duplicate_draws=100,
        mastery_tiers=[],
    )
    view = CollectionActionsView(guild_id=1001, user_id=11, collection=collection)

    for label, kind in (
        ("全重複をXP交換", "xp"),
        ("全重複をメダル交換", "medals"),
    ):
        button = next(
            item for item in view.children if getattr(item, "label", None) == label
        )
        interaction = _interaction(interaction_id=9104)
        await button.callback(interaction)
        send_args = cast(AsyncMock, interaction.response.send_message).await_args
        assert send_args is not None
        confirm = send_args.kwargs["view"]
        assert isinstance(confirm, RedemptionConfirmView)
        assert confirm.kind == kind
        assert confirm.quantities == {"c-card": 2, "r-card": 3}


@pytest.mark.parametrize(
    ("kind", "button_label", "rarity", "quantities", "reward", "endpoint"),
    [
        (
            "xp",
            "レアリティ別XP交換",
            "C",
            {"c-one": 2, "c-two": 1},
            17,
            "/redemptions/xp",
        ),
        (
            "medals",
            "レアリティ別メダル交換",
            "R",
            {"r-one": 3},
            15,
            "/redemptions/medals",
        ),
    ],
)
async def test_rarity_bulk_exchange_only_redeems_selected_unprotected_duplicates(
    kind: str,
    button_label: str,
    rarity: str,
    quantities: dict[str, int],
    reward: int,
    endpoint: str,
) -> None:
    def card(
        key: str,
        card_rarity: str,
        *,
        count: int,
        exchangeable: int,
        protected: bool = False,
        xp: int = 5,
        medals: int = 1,
    ) -> CafeCollectionCard:
        return CafeCollectionCard(
            key=key,
            name=key,
            rarity=card_rarity,
            description="説明",
            image_filename=f"{key}.jpg",
            count=count,
            redeemable_count=max(0, count - 1),
            lifetime_count=count,
            is_protected=protected,
            exchangeable_count=exchangeable,
            exchange_xp=xp,
            exchange_medals=medals,
        )

    collection = CafeCollection(
        cards=[
            card("c-one", "C", count=3, exchangeable=2),
            card("c-protected", "C", count=3, exchangeable=0, protected=True),
            card("c-two", "C", count=2, exchangeable=1, xp=7, medals=2),
            card("r-one", "R", count=4, exchangeable=3, xp=20, medals=5),
            card("r-single", "R", count=1, exchangeable=0),
        ],
        endgame_pity_active=False,
        endgame_pity_duplicate_draws=100,
        mastery_tiers=[],
    )
    actions = CollectionActionsView(guild_id=1001, user_id=11, collection=collection)
    button = next(
        item
        for item in actions.children
        if getattr(item, "label", None) == button_label
    )
    selection_interaction = _interaction(interaction_id=9101)
    await button.callback(selection_interaction)
    selection_args = cast(
        AsyncMock, selection_interaction.response.send_message
    ).await_args
    assert selection_args is not None
    selection = selection_args.kwargs["view"]
    assert isinstance(selection, RarityBulkExchangeView)
    rarity_select = cast(Any, selection.children[0])
    assert {option.value for option in rarity_select.options} == {"C", "R"}
    assert len(rarity_select.options) <= 25
    rarity_select._values = [rarity]

    confirm_interaction = _interaction(interaction_id=9102)
    await rarity_select.callback(confirm_interaction)
    confirm_args = cast(AsyncMock, confirm_interaction.response.send_message).await_args
    assert confirm_args is not None
    content = confirm_args.args[0]
    confirm = confirm_args.kwargs["view"]
    assert isinstance(confirm, RedemptionConfirmView)
    assert confirm.kind == kind
    assert confirm.quantities == quantities
    confirm_label = confirm.confirm.label
    assert confirm_label is not None
    assert ("XP" if kind == "xp" else "カフェメダル") in confirm_label
    assert f"{reward:,}" in content
    assert "最初の1枚と保護カードは残ります" in content

    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/authorize"):
            return httpx.Response(200, json={})
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "status": "redeemed",
                "reward_xp": reward if kind == "xp" else 0,
                "reward_medals": reward if kind == "medals" else 0,
                "medal_balance": reward,
                "items": [],
            },
        )

    api = CafeApiClient(
        "https://level.example.com",
        "cafe-secret",
        transport=httpx.MockTransport(handler),
    )
    transaction_interaction = _interaction(interaction_id=9103)
    cast(Any, transaction_interaction).client = SimpleNamespace(user=None, cafe_api=api)
    try:
        await confirm.confirm.callback(transaction_interaction)
    finally:
        await api.close()

    assert captured["path"].endswith(endpoint)
    assert captured["body"]["quantities"] == quantities
    assert captured["body"]["event_id"] == confirm.event_id
    assert captured["body"]["actor"]["guild_id"] == "1001"


async def test_large_collection_keeps_discord_select_options_within_limit() -> None:
    cards = [
        CafeCollectionCard(
            key=f"card-{index}",
            name=f"カード{index}",
            rarity="C",
            description="説明",
            image_filename=f"card-{index}.jpg",
            count=2,
            redeemable_count=1,
            lifetime_count=2,
            is_protected=False,
            exchangeable_count=1,
            exchange_xp=5,
            exchange_medals=1,
        )
        for index in range(1001)
    ]
    collection = CafeCollection(
        cards=cards,
        endgame_pity_active=False,
        endgame_pity_duplicate_draws=100,
        mastery_tiers=[],
    )
    view = CollectionActionsView(guild_id=1001, user_id=11, collection=collection)

    options = [
        component["options"]
        for row in view.to_components()
        for component in row["components"]
        if "options" in component
    ]
    assert options
    assert all(1 <= len(group) <= 25 for group in options)

    redeem = next(
        item
        for item in view.children
        if getattr(item, "label", None) == "重複を選んでXP交換"
    )
    interaction = _interaction(interaction_id=5010)
    await redeem.callback(interaction)
    send_args = cast(AsyncMock, interaction.response.send_message).await_args
    assert send_args is not None
    rarity_view = send_args.kwargs["view"]
    assert isinstance(rarity_view, RarityPageView)
    assert all(
        len(component["options"]) <= 25
        for row in rarity_view.to_components()
        for component in row["components"]
        if "options" in component
    )

    seen = set()
    for page in range(41):
        choice = CardChoiceView(
            guild_id=1001, user_id=11, cards=cards, action="redeem_xp", page=page
        )
        seen.update(cast(Any, choice.children[-1]).cards_by_key)
        assert 1 <= len(cast(Any, choice.children[-1]).options) <= 25
    assert seen == {card.key for card in cards}

    first_choice = CardChoiceView(
        guild_id=1001, user_id=11, cards=cards, action="redeem_xp"
    )
    next_interaction = _interaction(interaction_id=5015)
    await first_choice.next_page.callback(next_interaction)
    edit_args = cast(AsyncMock, next_interaction.response.edit_message).await_args
    assert edit_args is not None
    second_choice = edit_args.kwargs["view"]
    assert isinstance(second_choice, CardChoiceView)
    assert second_choice.page == 1
    assert "card-25" in cast(Any, second_choice.children[-1]).cards_by_key


async def test_card_search_finds_a_late_duplicate() -> None:
    cards = [
        CafeCollectionCard(
            key=f"card-{index}",
            name=f"カード{index}",
            rarity="C",
            description="説明",
            image_filename=f"card-{index}.jpg",
            count=2,
            redeemable_count=1,
            lifetime_count=2,
            is_protected=False,
            exchangeable_count=1,
            exchange_xp=5,
            exchange_medals=1,
        )
        for index in range(1000)
    ]
    view = RarityPageView(guild_id=1001, user_id=11, cards=cards, action="redeem_xp")
    search = next(
        item
        for item in view.children
        if getattr(item, "label", None) == "カード名で探す"
    )
    interaction = _interaction(interaction_id=5011)
    cast(Any, interaction.response).send_modal = AsyncMock()
    await search.callback(interaction)
    modal_args = cast(AsyncMock, interaction.response.send_modal).await_args
    assert modal_args is not None
    modal = modal_args.args[0]
    modal.query._value = "カード999"
    api = Mock(spec=CafeApiClient)
    api.authorize = AsyncMock()
    result_interaction = _interaction(interaction_id=5012)
    cast(Any, result_interaction.client).cafe_api = api

    await modal.on_submit(result_interaction)

    result_args = cast(AsyncMock, result_interaction.response.send_message).await_args
    assert result_args is not None
    result = result_args.kwargs["view"]
    assert isinstance(result, CardChoiceView)
    assert list(cast(Any, result.children[-1]).cards_by_key) == ["card-999"]


async def test_custom_quantity_accepts_more_than_four_digits() -> None:
    card = CafeCollectionCard(
        key="spent-tea",
        name="出がらしティー",
        rarity="C",
        description="説明",
        image_filename="spent-tea.jpg",
        count=100001,
        redeemable_count=100000,
        lifetime_count=100001,
        is_protected=False,
        exchangeable_count=100000,
        exchange_xp=5,
        exchange_medals=1,
    )
    modal = CustomQuantityModal(guild_id=1001, user_id=11, card=card)
    assert modal.quantity.max_length == 6
    modal.quantity._value = "50000"
    api = Mock(spec=CafeApiClient)
    api.authorize = AsyncMock()
    interaction = _interaction(interaction_id=5013)
    cast(Any, interaction.client).cafe_api = api

    await modal.on_submit(interaction)

    confirm_args = cast(AsyncMock, interaction.response.send_message).await_args
    assert confirm_args is not None
    confirm = confirm_args.kwargs["view"]
    assert isinstance(confirm, RedemptionConfirmView)
    assert confirm.quantities == {"spent-tea": 50000}


async def test_xp_exchange_uses_confirmation_interaction_as_idempotency_key() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(cast(dict[str, Any], json.loads(request.content)))
        return httpx.Response(
            200,
            json={
                "status": "redeemed",
                "reward_xp": 30,
                "reward_medals": 0,
                "items": [],
            },
        )

    api = CafeApiClient(
        "https://level.example.com",
        "cafe-secret",
        transport=httpx.MockTransport(handler),
    )
    interaction = _interaction(interaction_id=8002)
    cast(Any, interaction).client = SimpleNamespace(user=None, cafe_api=api)
    cast(Any, interaction.response).edit_message = AsyncMock()
    view = RedemptionConfirmView(
        guild_id=1001,
        user_id=11,
        quantities={"spent-tea": 1},
        kind="xp",
        confirm_label="このカードを交換する",
        unavailable_message="所持数が変わりました。",
    )
    button = cast(discord.ui.Button[discord.ui.View], view.children[0])
    try:
        await button.callback(interaction)
    finally:
        await api.close()

    assert captured["event_id"] == view.event_id
    assert captured["quantities"] == {"spent-tea": 1}
    assert captured["actor"]["guild_id"] == "1001"


async def test_medal_confirmation_has_no_extra_cancel_button() -> None:
    xp_view = RedemptionConfirmView(
        guild_id=1001,
        user_id=11,
        quantities={"spent-tea": 1},
        kind="xp",
        confirm_label="このカードを交換する",
        unavailable_message="所持数が変わりました。",
    )
    medal_view = RedemptionConfirmView(
        guild_id=1001,
        user_id=11,
        quantities={"spent-tea": 1},
        kind="medals",
        confirm_label="メダルへ交換する",
        unavailable_message="所持数が変わりました。",
    )

    assert [getattr(child, "label", None) for child in xp_view.children] == [
        "このカードを交換する",
        "キャンセル",
    ]
    assert [getattr(child, "label", None) for child in medal_view.children] == [
        "メダルへ交換する"
    ]
