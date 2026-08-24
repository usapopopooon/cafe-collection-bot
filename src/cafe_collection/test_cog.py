from typing import Any, cast
from unittest.mock import AsyncMock, Mock

import discord
import pytest
from discord import app_commands

from cafe_collection import cog as cog_module
from cafe_collection.cog import CafeCog, DrawConfirmView, _actor
from cafe_collection.level_api import (
    CafeActor,
    CafeApiClient,
    CafeAvailability,
    CafeCollection,
    CafeCollectionCard,
    CafeDrawBatch,
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
    interaction.user = member
    interaction.permissions = permissions
    interaction.response = response
    interaction.followup = followup
    return cast(discord.Interaction, interaction)


def _wallet(available_xp: int = 100) -> CafeWallet:
    return CafeWallet(
        total_xp=available_xp,
        spent_xp=0,
        available_xp=available_xp,
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
    cog = CafeCog(cast(CafeApiClient, api))

    command = cast(Any, CafeCog.draw)
    await command.callback(cog, initial_interaction, 1)

    api.availability.assert_awaited_once_with(initial_actor, count=1)
    api.draw.assert_not_awaited()
    send = cast(AsyncMock, initial_interaction.followup.send)
    assert send.await_args is not None
    view = send.await_args.kwargs["view"]
    assert isinstance(view, DrawConfirmView)

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
        return_value=CafeCollection(cards=[selected_card, other_card])
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
