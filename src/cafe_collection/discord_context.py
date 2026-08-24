"""Discord interaction identity and error boundary for Cafe features."""

from __future__ import annotations

import discord

from cafe_collection.level_api import (
    CafeAccessDenied,
    CafeActor,
    CafeApiClient,
    CafeApiError,
)


def actor_from_interaction(interaction: discord.Interaction) -> CafeActor | None:
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


def api_from_interaction(interaction: discord.Interaction) -> CafeApiClient | None:
    api = getattr(interaction.client, "cafe_api", None)
    return api if isinstance(api, CafeApiClient) else None


async def send_api_error(interaction: discord.Interaction, error: CafeApiError) -> None:
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
