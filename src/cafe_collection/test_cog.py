import json
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, Mock

import discord
import httpx
import pytest
from discord import app_commands

from cafe_collection import cog as cog_module
from cafe_collection.cog import (
    CafeCog,
    CafePanelDrawButton,
    CafePanelView,
    DrawConfirmView,
    _draw,
)
from cafe_collection.collection_ui import (
    CollectionActionsView,
    RedemptionConfirmView,
    _collection_summary,
)
from cafe_collection.discord_context import actor_from_interaction as _actor
from cafe_collection.level_api import (
    CafeActor,
    CafeApiClient,
    CafeAvailability,
    CafeCapabilities,
    CafeCollection,
    CafeCollectionCard,
    CafeCosmetic,
    CafeDrawBatch,
    CafeMasterySummary,
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
        api_version=3,
        catalog_size=361,
        asset_count=363,
        asset_manifest_sha256="test",
        paid_draw_cost_xp=20,
        hourly_draw_limit=10,
        minimum_draw_reward_xp=10,
        maximum_draw_reward_xp=5000,
    )


def _drawn_result() -> CafeDrawBatch:
    wallet = _wallet()
    return CafeDrawBatch(
        status="drawn",
        draws=[],
        wallet_before=wallet,
        wallet_after=wallet,
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
    cog = CafeCog(cast(CafeApiClient, api))

    command = cast(Any, CafeCog.draw)
    await command.callback(cog, interaction, 2)

    api.availability.assert_awaited_once_with(actor, count=2)
    api.draw.assert_awaited_once_with(
        actor,
        event_id="cafe-bot:5001",
        display_name="カフェ客",
        count=2,
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
    cog = CafeCog(cast(CafeApiClient, api))

    command = cast(Any, CafeCog.draw)
    await command.callback(cog, initial_interaction, 1)

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
        "最低獲得: **10 XP**\n"
        "抽選後: **90 XP以上**\n"
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
        event_id="cafe-bot:5002",
        display_name="カフェ客",
        count=1,
        expected_cost_xp=20,
    )


async def test_collection_wires_actor_and_selected_rarity(
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
    rendered_cards: list[CafeCollectionCard] = []

    def render(cards: list[CafeCollectionCard]) -> tuple[bytes, ...]:
        rendered_cards.extend(cards)
        return (b"\xff\xd8\xff\xd9",)

    monkeypatch.setattr(cog_module, "render_collection_pages", render)
    cog = CafeCog(cast(CafeApiClient, api))

    command = cast(Any, CafeCog.collection)
    await command.callback(
        cog,
        interaction,
        app_commands.Choice(name="N", value="C"),
    )

    api.collection.assert_awaited_once_with(actor)
    assert rendered_cards == [selected_card]


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
        "1枚引く",
        "まとめて引く（最大10枚）",
        "自分の棚・重複交換",
        "自分のXP・残り枠",
    }
    draw_request = next(
        payload for path, payload in requests if path.endswith("/draws")
    )
    assert draw_request["event_id"] == "cafe-bot:7001"


def test_cafe_command_group_exposes_user_and_admin_feature_parity() -> None:
    assert {command.name for command in CafeCog.__cog_app_commands__} == {
        "draw",
        "collection",
        "balance",
        "protect",
        "stats",
        "access-role",
        "panel",
        "ledger",
        "ranking",
    }
    access_role = next(
        command
        for command in CafeCog.__cog_app_commands__
        if command.name == "access-role"
    )
    assert isinstance(access_role, app_commands.Group)
    assert {command.name for command in access_role.commands} == {
        "add",
        "remove",
        "list",
    }


@pytest.mark.parametrize("placement", ["panel", "ledger", "ranking"])
async def test_admin_command_saves_exact_channel_and_message_mapping(
    placement: str,
) -> None:
    saved_payloads: list[dict[str, Any]] = []
    layout: dict[str, str | None] = {
        "panel_channel_id": None,
        "panel_message_id": None,
        "ledger_channel_id": None,
        "ledger_message_id": None,
        "ranking_channel_id": None,
        "ranking_message_id": None,
    }
    layout[f"{placement}_channel_id"] = "2001"
    layout[f"{placement}_message_id"] = "3001"

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/capabilities"):
            return httpx.Response(
                200,
                json={
                    "api_version": 3,
                    "catalog_size": 361,
                    "asset_count": 363,
                    "asset_manifest_sha256": "test",
                    "paid_draw_cost_xp": 20,
                    "hourly_draw_limit": 10,
                    "minimum_draw_reward_xp": 10,
                    "maximum_draw_reward_xp": 5000,
                },
            )
        if path.endswith("/rankings"):
            return httpx.Response(
                200,
                json={
                    "participant_count": 0,
                    "total_draws": 0,
                    "captured_at": "2026-08-24T00:00:00Z",
                    "categories": [],
                },
            )
        if path.endswith("/placements"):
            saved_payloads.append(cast(dict[str, Any], json.loads(request.content)))
            return httpx.Response(200, json=layout)
        return httpx.Response(200, json=layout)

    api = CafeApiClient(
        "https://level.example.com",
        "cafe-secret",
        transport=httpx.MockTransport(handler),
    )
    guild = Mock(spec=discord.Guild)
    guild.id = 1001
    guild.me = Mock(spec=discord.Member)
    target = Mock(spec=discord.TextChannel)
    target.id = 2001
    target.guild = guild
    target.mention = "<#2001>"
    permissions = Mock(spec=discord.Permissions)
    permissions.view_channel = True
    permissions.send_messages = True
    permissions.embed_links = True
    permissions.read_message_history = True
    permissions.attach_files = True
    target.permissions_for.return_value = permissions
    bot_user = SimpleNamespace(id=4001)
    author = SimpleNamespace(id=bot_user.id)
    message = Mock(spec=discord.Message)
    message.id = 3001
    message.author = author
    message.edit = AsyncMock(return_value=message)
    target.fetch_message = AsyncMock(return_value=message)
    target.send = AsyncMock()
    interaction = _interaction(interaction_id=7002, manage_guild=True)
    cast(Any, interaction).guild = guild
    cast(Any, interaction).channel = target
    cast(Any, interaction).client = SimpleNamespace(user=bot_user, cafe_api=api)
    cog = CafeCog(api)

    command = cast(Any, getattr(CafeCog, placement))
    try:
        await command.callback(
            cog,
            interaction,
            None if placement == "ledger" else target,
        )
    finally:
        await api.close()

    assert len(saved_payloads) == 1
    assert saved_payloads[0]["placement"] == placement
    assert saved_payloads[0]["channel_id"] == "2001"
    assert saved_payloads[0]["message_id"] == "3001"
    message.edit.assert_awaited_once()
    target.send.assert_not_awaited()


async def test_maximum_draw_matches_old_panel_affordable_count() -> None:
    interaction = _interaction(interaction_id=8001)
    actor = CafeActor(
        guild_id="1001",
        user_id="11",
        role_ids=["9001"],
        can_manage_guild=False,
    )
    api = Mock(spec=CafeApiClient)
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
    assert view.count == 3
    assert view.expected_cost_xp == 40
    assert view.actor == actor
    assert send.await_args.args[0] == (
        "**3枚をまとめて引きます**（本日の無料1枚を含む）。\n"
        "現在XP: **20 XP**\n"
        "消費: **40 XP**\n"
        "最低獲得: **30 XP**\n"
        "抽選後: **10 XP以上**\n"
        "この時間の残り枠: 5 → **2回**\n"
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


async def test_collection_actions_include_every_old_collection_operation() -> None:
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
        "お気に入り",
        "カード保護",
        "個別XP交換",
        "全重複をXPへ",
        "全重複をメダルへ",
        "メダル・棚テーマ",
        "セットメニュー",
    }


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
    )
    button = cast(discord.ui.Button[discord.ui.View], view.children[0])
    try:
        await button.callback(interaction)
    finally:
        await api.close()

    assert captured["event_id"] == "cafe-bot:redemption:8002"
    assert captured["quantities"] == {"spent-tea": 1}
    assert captured["actor"]["guild_id"] == "1001"
