"""Typed client for level-bot's transactional Cafe Collection API."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, TypeVar

import httpx
from pydantic import BaseModel, ValidationError
from pydantic import Field as PydanticField

ModelT = TypeVar("ModelT", bound=BaseModel)


class CafeApiError(RuntimeError):
    """Raised when level-bot cannot complete a Cafe operation."""


class CafeAccessDenied(CafeApiError):
    """Raised when level-bot rejects the member's configured access roles."""


class CafeActor(BaseModel):
    guild_id: str
    user_id: str
    role_ids: list[str]
    can_manage_guild: bool


class CafeCapabilities(BaseModel):
    api_version: int
    catalog_size: int
    asset_count: int
    asset_manifest_sha256: str
    paid_draw_cost_xp: int
    hourly_draw_limit: int
    minimum_draw_reward_xp: int
    maximum_draw_reward_xp: int
    draw_reward_xp_by_rarity: dict[str, int]
    exchange_xp_by_rarity: dict[str, int]
    ranking_category_totals: dict[str, int]
    set_count: int


class CafeWallet(BaseModel):
    total_xp: int
    spent_xp: int
    available_xp: int


class CafeAvailability(BaseModel):
    wallet: CafeWallet
    has_free_draw: bool
    hourly_remaining: int
    requested_count: int
    cost_xp: int


class CafeDraw(BaseModel):
    event_id: str
    batch_position: int
    reward_key: str
    reward_name: str
    reward_description: str
    rarity: str
    image_filename: str
    draw_type: str
    cost_xp: int
    reward_xp: int
    exchange_xp: int
    was_duplicate: bool
    owned_count: int
    collected_count: int


class CafeDrawBatch(BaseModel):
    status: Literal[
        "drawn",
        "confirmation_required",
        "insufficient_xp",
        "hourly_limit",
        "conflict",
    ]
    draws: list[CafeDraw]
    wallet_before: CafeWallet
    wallet_after: CafeWallet


class CafeCollectionCard(BaseModel):
    key: str
    name: str
    rarity: str
    description: str
    image_filename: str
    count: int
    redeemable_count: int
    lifetime_count: int
    is_protected: bool
    exchangeable_count: int = 0
    exchange_xp: int = 0
    exchange_medals: int = 0
    mastery_name: str | None = None
    mastery_emoji: str | None = None


class CafeCosmetic(BaseModel):
    key: str
    name: str
    cost_medals: int
    color: int
    decoration: str


class CafeSet(BaseModel):
    key: str
    name: str
    description: str
    completed: bool
    missing_card_names: list[str]


class CafeMasterySummary(BaseModel):
    name: str
    emoji: str
    card_count: int


class CafeCollection(BaseModel):
    cards: list[CafeCollectionCard]
    favorite_reward_key: str | None = None
    duplicate_draw_streak: int = 0
    endgame_pity_active: bool
    endgame_pity_duplicate_draws: int
    mastery_tiers: list[CafeMasterySummary]
    medal_balance: int = 0
    active_cosmetic: CafeCosmetic | None = None
    cosmetics: list[CafeCosmetic] = PydanticField(default_factory=list)
    sets: list[CafeSet] = PydanticField(default_factory=list)


class CafeCardSetting(BaseModel):
    status: Literal["updated", "unavailable"]
    reward_key: str | None
    reward_name: str | None
    protected: bool | None = None


class CafeRedemptionItem(BaseModel):
    reward_key: str
    reward_name: str
    rarity: str
    quantity: int
    reward_per_card: int
    reward_total: int


class CafeRedemption(BaseModel):
    status: Literal["redeemed", "unavailable"]
    reward_xp: int
    reward_medals: int
    medal_balance: int | None = None
    items: list[CafeRedemptionItem]


class CafeCosmeticResult(BaseModel):
    status: Literal["equipped", "insufficient", "unavailable"]
    cosmetic: CafeCosmetic | None
    balance: int


class CafeAnalytics(BaseModel):
    draws_today: int
    draws_7d: int
    total_draws: int
    active_today: int
    active_7d: int
    total_users: int
    new_7d: int
    duplicate_7d: int
    rarity_7d: dict[str, int]
    spent_xp_7d: int
    draw_reward_xp_7d: int
    redemption_xp_7d: int
    completed_users: int


class CafeAccessRoles(BaseModel):
    role_ids: list[str]
    changed: bool | None = None


class CafeLayout(BaseModel):
    panel_channel_id: str | None
    panel_message_id: str | None
    ledger_channel_id: str | None
    ledger_message_id: str | None
    ranking_channel_id: str | None
    ranking_message_id: str | None


class CafeLedgerDrawBatch(BaseModel):
    event_id: str
    user_id: str
    created_at: datetime
    draws: list[CafeDraw]


class CafeLedgerRedemption(BaseModel):
    event_id: str
    user_id: str
    created_at: datetime
    reward_xp: int
    items: list[CafeRedemptionItem]


class CafeLedgerPending(BaseModel):
    ledger_channel_id: str | None
    draw_batches: list[CafeLedgerDrawBatch]
    redemptions: list[CafeLedgerRedemption]


class CafeLedgerDelivered(BaseModel):
    delivered: bool


class CafeRankingEntry(BaseModel):
    rank: int
    user_id: str
    collection_count: int
    mastery_score: int
    familiar_cards: int
    regular_cards: int
    signature_cards: int
    completed_sets: int
    rare_collection_count: int
    rare_r_count: int
    rare_sr_count: int
    rare_ssr_count: int
    rare_ur_count: int
    rare_mythic_count: int
    treasure_collection_count: int
    n_collection_count: int
    n_mastery_score: int
    n_signature_cards: int
    coffee_collection_count: int
    coffee_mastery_score: int
    coffee_signature_cards: int
    tea_collection_count: int
    tea_mastery_score: int
    tea_signature_cards: int
    sweets_collection_count: int
    sweets_mastery_score: int
    sweets_signature_cards: int
    culture_collection_count: int
    culture_mastery_score: int
    culture_signature_cards: int


class CafeRankingCategory(BaseModel):
    key: str
    entries: list[CafeRankingEntry]
    viewer_entry: CafeRankingEntry | None = None


class CafeRankings(BaseModel):
    participant_count: int
    total_draws: int
    captured_at: datetime
    category_totals: dict[str, int]
    set_count: int
    categories: list[CafeRankingCategory]


@dataclass
class CafeApiClient:
    base_url: str
    token: str = field(repr=False)
    transport: httpx.AsyncBaseTransport | None = field(default=None, repr=False)
    _client: httpx.AsyncClient = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=httpx.Timeout(10.0),
            transport=self.transport,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = await self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise CafeApiError("level-bot APIへ接続できません") from exc
        if response.status_code == 403:
            role_ids: list[str] = []
            try:
                detail = response.json().get("detail", {})
                if isinstance(detail, dict) and isinstance(
                    detail.get("role_ids"), list
                ):
                    role_ids = [str(value) for value in detail["role_ids"]]
            except ValueError:
                pass
            visible = role_ids[:20]
            roles = "、".join(f"<@&{role_id}>" for role_id in visible)
            if len(role_ids) > len(visible):
                roles += f"、ほか {len(role_ids) - len(visible)}件"
            message = "この機能を利用できるロールがありません。"
            if roles:
                message += f"\n利用可能なロール: {roles}"
            raise CafeAccessDenied(message)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise CafeApiError(
                f"level-bot APIがエラーを返しました ({response.status_code})"
            ) from exc
        try:
            return response.json()
        except ValueError as exc:
            raise CafeApiError("level-bot APIの応答を読み取れません") from exc

    @staticmethod
    def _validate(model: type[ModelT], data: Any) -> ModelT:
        try:
            return model.model_validate(data)
        except ValidationError as exc:
            raise CafeApiError("level-bot APIのバージョンが一致しません") from exc

    async def capabilities(self) -> CafeCapabilities:
        data = await self._request(
            "GET", "/api/v1/integrations/cafe-collection/capabilities"
        )
        return self._validate(CafeCapabilities, data)

    async def authorize(self, actor: CafeActor) -> None:
        await self._request(
            "POST",
            "/api/v1/integrations/cafe-collection/authorize",
            json={"actor": actor.model_dump()},
        )

    async def availability(self, actor: CafeActor, *, count: int) -> CafeAvailability:
        data = await self._request(
            "POST",
            "/api/v1/integrations/cafe-collection/draw-availability",
            json={"actor": actor.model_dump(), "count": count},
        )
        return self._validate(CafeAvailability, data)

    async def draw(
        self,
        actor: CafeActor,
        *,
        event_id: str,
        display_name: str,
        count: int,
        expected_cost_xp: int,
    ) -> CafeDrawBatch:
        data = await self._request(
            "POST",
            "/api/v1/integrations/cafe-collection/draws",
            json={
                "actor": actor.model_dump(),
                "event_id": event_id,
                "display_name": display_name,
                "count": count,
                "expected_cost_xp": expected_cost_xp,
            },
        )
        return self._validate(CafeDrawBatch, data)

    async def collection(self, actor: CafeActor) -> CafeCollection:
        data = await self._request(
            "POST",
            "/api/v1/integrations/cafe-collection/collection",
            json={"actor": actor.model_dump()},
        )
        return self._validate(CafeCollection, data)

    async def collection_preview(self, actor: CafeActor) -> CafeCollection:
        data = await self._request(
            "POST",
            "/api/v1/integrations/cafe-collection/collection-preview",
            json={"actor": actor.model_dump()},
        )
        return self._validate(CafeCollection, data)

    async def set_favorite(
        self, actor: CafeActor, *, reward_key: str
    ) -> CafeCardSetting:
        data = await self._request(
            "POST",
            "/api/v1/integrations/cafe-collection/favorite",
            json={"actor": actor.model_dump(), "reward_key": reward_key},
        )
        return self._validate(CafeCardSetting, data)

    async def set_protection(
        self,
        actor: CafeActor,
        *,
        reward_key: str,
        protected: bool,
    ) -> CafeCardSetting:
        data = await self._request(
            "POST",
            "/api/v1/integrations/cafe-collection/protection",
            json={
                "actor": actor.model_dump(),
                "reward_key": reward_key,
                "protected": protected,
            },
        )
        return self._validate(CafeCardSetting, data)

    async def redeem_xp(
        self,
        actor: CafeActor,
        *,
        event_id: str,
        display_name: str,
        quantities: dict[str, int],
    ) -> CafeRedemption:
        data = await self._request(
            "POST",
            "/api/v1/integrations/cafe-collection/redemptions/xp",
            json={
                "actor": actor.model_dump(),
                "event_id": event_id,
                "display_name": display_name,
                "quantities": quantities,
            },
        )
        return self._validate(CafeRedemption, data)

    async def redeem_medals(
        self,
        actor: CafeActor,
        *,
        event_id: str,
        display_name: str,
        quantities: dict[str, int],
    ) -> CafeRedemption:
        data = await self._request(
            "POST",
            "/api/v1/integrations/cafe-collection/redemptions/medals",
            json={
                "actor": actor.model_dump(),
                "event_id": event_id,
                "display_name": display_name,
                "quantities": quantities,
            },
        )
        return self._validate(CafeRedemption, data)

    async def equip_cosmetic(
        self, actor: CafeActor, *, cosmetic_key: str
    ) -> CafeCosmeticResult:
        data = await self._request(
            "POST",
            "/api/v1/integrations/cafe-collection/cosmetics/equip",
            json={"actor": actor.model_dump(), "cosmetic_key": cosmetic_key},
        )
        return self._validate(CafeCosmeticResult, data)

    async def analytics(self, actor: CafeActor) -> CafeAnalytics:
        data = await self._request(
            "POST",
            "/api/v1/integrations/cafe-collection/analytics",
            json={"actor": actor.model_dump()},
        )
        return self._validate(CafeAnalytics, data)

    async def access_roles(self, actor: CafeActor) -> CafeAccessRoles:
        data = await self._request(
            "POST",
            "/api/v1/integrations/cafe-collection/access-roles",
            json={"actor": actor.model_dump()},
        )
        return self._validate(CafeAccessRoles, data)

    async def add_access_role(
        self, actor: CafeActor, *, role_id: str
    ) -> CafeAccessRoles:
        data = await self._request(
            "POST",
            "/api/v1/integrations/cafe-collection/access-roles/add",
            json={"actor": actor.model_dump(), "role_id": role_id},
        )
        return self._validate(CafeAccessRoles, data)

    async def remove_access_role(
        self, actor: CafeActor, *, role_id: str
    ) -> CafeAccessRoles:
        data = await self._request(
            "POST",
            "/api/v1/integrations/cafe-collection/access-roles/remove",
            json={"actor": actor.model_dump(), "role_id": role_id},
        )
        return self._validate(CafeAccessRoles, data)

    async def layout(self, actor: CafeActor) -> CafeLayout:
        data = await self._request(
            "POST",
            "/api/v1/integrations/cafe-collection/discord-layout",
            json={"actor": actor.model_dump()},
        )
        return self._validate(CafeLayout, data)

    async def save_placement(
        self,
        actor: CafeActor,
        *,
        placement: Literal["panel", "ledger", "ranking"],
        channel_id: str,
        message_id: str | None,
    ) -> CafeLayout:
        data = await self._request(
            "POST",
            "/api/v1/integrations/cafe-collection/discord-layout/placements",
            json={
                "actor": actor.model_dump(),
                "placement": placement,
                "channel_id": channel_id,
                "message_id": message_id,
            },
        )
        return self._validate(CafeLayout, data)

    async def pending_ledger(self, *, guild_id: str) -> CafeLedgerPending:
        data = await self._request(
            "POST",
            "/api/v1/integrations/cafe-collection/ledger/pending",
            json={"guild_id": guild_id},
        )
        return self._validate(CafeLedgerPending, data)

    async def mark_ledger_delivered(
        self,
        *,
        guild_id: str,
        record_type: Literal["draw", "redemption"],
        event_id: str,
        message_id: str,
    ) -> CafeLedgerDelivered:
        data = await self._request(
            "POST",
            "/api/v1/integrations/cafe-collection/ledger/delivered",
            json={
                "guild_id": guild_id,
                "record_type": record_type,
                "event_id": event_id,
                "message_id": message_id,
            },
        )
        return self._validate(CafeLedgerDelivered, data)

    async def rankings(self, actor: CafeActor) -> CafeRankings:
        data = await self._request(
            "POST",
            "/api/v1/integrations/cafe-collection/rankings",
            json={"actor": actor.model_dump()},
        )
        return self._validate(CafeRankings, data)
