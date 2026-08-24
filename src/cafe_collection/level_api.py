"""Typed client for level-bot's transactional Cafe Collection API."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

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


class CafeCollection(BaseModel):
    cards: list[CafeCollectionCard]


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
            raise CafeAccessDenied("この機能を利用できるロールがありません")
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
