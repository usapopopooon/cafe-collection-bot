import httpx
import pytest

from cafe_collection.level_api import (
    CafeAccessDenied,
    CafeActor,
    CafeApiClient,
    CafeApiError,
    CafeApiUnavailable,
)


def _actor() -> CafeActor:
    return CafeActor(
        guild_id="1001",
        user_id="11",
        role_ids=["9001"],
        can_manage_guild=False,
    )


async def test_client_uses_dedicated_bearer_token_and_actor_mapping() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer cafe-secret"
        assert request.url.path.endswith("/draw-availability")
        assert b'"guild_id":"1001"' in request.content
        return httpx.Response(
            200,
            json={
                "wallet": {"total_xp": 100, "spent_xp": 20, "available_xp": 80},
                "has_free_draw": False,
                "hourly_remaining": 9,
                "requested_count": 2,
                "cost_xp": 40,
            },
        )

    client = CafeApiClient(
        "https://level.example.com",
        "cafe-secret",
        transport=httpx.MockTransport(handler),
    )
    try:
        result = await client.availability(_actor(), count=2)
    finally:
        await client.close()

    assert result.cost_xp == 40
    assert result.wallet.available_xp == 80


async def test_client_maps_access_denial_without_exposing_response_body() -> None:
    client = CafeApiClient(
        "https://level.example.com",
        "cafe-secret",
        transport=httpx.MockTransport(lambda _request: httpx.Response(403)),
    )
    try:
        with pytest.raises(CafeAccessDenied):
            await client.collection(_actor())
    finally:
        await client.close()


async def test_client_maps_incompatible_response_to_operational_error() -> None:
    client = CafeApiClient(
        "https://level.example.com",
        "cafe-secret",
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json={"unexpected": True})
        ),
    )
    try:
        with pytest.raises(CafeApiError, match="バージョンが一致"):
            await client.capabilities()
    finally:
        await client.close()


async def test_client_distinguishes_temporarily_unavailable_api() -> None:
    client = CafeApiClient(
        "https://level.example.com",
        "cafe-secret",
        transport=httpx.MockTransport(lambda _request: httpx.Response(503)),
    )
    try:
        with pytest.raises(CafeApiUnavailable, match="503"):
            await client.capabilities()
    finally:
        await client.close()
