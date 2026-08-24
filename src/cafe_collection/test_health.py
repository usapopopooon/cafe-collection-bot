import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from cafe_collection import assets
from cafe_collection.config import ApiSettings
from cafe_collection.health import app, create_app
from cafe_collection.public_api import PublicCafeApiClient


async def test_healthz_reports_process_liveness() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readyz_checks_image_bundle() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


async def test_readyz_returns_503_when_image_bundle_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(assets, "asset_bundle_ready", lambda: False)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/readyz")

    assert response.status_code == 503
    assert response.json() == {"detail": "image bundle unavailable"}


async def test_card_image_serves_bundled_asset_and_rejects_unknown_key() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        image = await client.get("/api/v1/public/cafe-collection/cards/spent-tea/image")
        unknown = await client.get(
            "/api/v1/public/cafe-collection/cards/not-a-card/image"
        )

    assert image.status_code == 200
    assert image.headers["content-type"] == "image/jpeg"
    assert image.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert unknown.status_code == 404


async def test_public_data_routes_preserve_level_bot_contract() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/catalog"):
            return httpx.Response(
                200,
                json={
                    "total_cards": 433,
                    "cards": [
                        {
                            "key": "spent-tea",
                            "image_url": (
                                "/api/v1/public/cafe-collection/cards/"
                                "spent-tea/image?v=abc123"
                            ),
                        }
                    ],
                },
                headers={"Cache-Control": "public, max-age=3600"},
            )
        if request.url.path.endswith("/leaderboards"):
            return httpx.Response(200, json={"guild_id": "guild-1"})
        return httpx.Response(
            404,
            json={"detail": "Collection profile not found"},
            headers={"Cache-Control": "public, max-age=300"},
        )

    upstream = PublicCafeApiClient(
        "https://level.example.com",
        transport=httpx.MockTransport(handler),
    )
    test_app = create_app(
        settings=ApiSettings(external_api_key=SecretStr("shared-public-jwt")),
        public_api_client=upstream,
    )
    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test",
        headers={"Authorization": "Bearer shared-public-jwt"},
    ) as client:
        catalog = await client.get("/api/v1/public/cafe-collection/catalog")
        rankings = await client.get(
            "/api/v1/public/cafe-collection/guilds/guild-1/leaderboards"
        )
        profile = await client.get(
            "/api/v1/public/cafe-collection/guilds/guild-1/profiles/missing"
        )
    await upstream.close()

    assert catalog.status_code == 200
    assert catalog.json()["cards"][0]["image_url"].endswith("/spent-tea/image?v=abc123")
    assert catalog.headers["cache-control"] == "public, max-age=3600"
    assert rankings.json() == {"guild_id": "guild-1"}
    assert profile.status_code == 404
    assert profile.json() == {"detail": "Collection profile not found"}
    assert [request.url.path for request in requests] == [
        "/api/v1/public/cafe-collection/catalog",
        "/api/v1/public/cafe-collection/guilds/guild-1/leaderboards",
        "/api/v1/public/cafe-collection/guilds/guild-1/profiles/missing",
    ]
    assert all("authorization" not in request.headers for request in requests)


async def test_public_api_allows_site_origin_with_shared_public_jwt() -> None:
    upstream = PublicCafeApiClient(
        "https://level.example.com",
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json={"total_cards": 433})
        ),
    )
    test_app = create_app(
        settings=ApiSettings(external_api_key=SecretStr("shared-public-jwt")),
        public_api_client=upstream,
    )
    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/api/v1/public/cafe-collection/catalog",
            headers={
                "Origin": "https://chill-cafe.site",
                "Authorization": "Bearer shared-public-jwt",
            },
        )
    await upstream.close()

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "https://chill-cafe.site"
    )


async def test_public_api_allows_authorization_header_preflight() -> None:
    upstream = PublicCafeApiClient(
        "https://level.example.com",
        transport=httpx.MockTransport(lambda _request: httpx.Response(404)),
    )
    test_app = create_app(
        settings=ApiSettings(external_api_key=SecretStr("shared-public-jwt")),
        public_api_client=upstream,
    )
    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test",
    ) as client:
        response = await client.options(
            "/api/v1/public/cafe-collection/catalog",
            headers={
                "Origin": "https://chill-cafe.site",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization",
            },
        )
    await upstream.close()

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "https://chill-cafe.site"
    )
    assert "authorization" in response.headers["access-control-allow-headers"].lower()


async def test_public_api_returns_502_when_level_bot_is_unavailable() -> None:
    def fail(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("unavailable")

    upstream = PublicCafeApiClient(
        "https://level.example.com",
        transport=httpx.MockTransport(fail),
    )
    test_app = create_app(
        settings=ApiSettings(external_api_key=SecretStr("shared-public-jwt")),
        public_api_client=upstream,
    )
    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/api/v1/public/cafe-collection/catalog",
            headers={"Authorization": "Bearer shared-public-jwt"},
        )
    await upstream.close()

    assert response.status_code == 502
    assert response.json() == {"detail": "level-bot Cafe Collection API unavailable"}


async def test_public_data_requires_shared_public_jwt_but_images_stay_public() -> None:
    settings = ApiSettings(external_api_key=SecretStr("shared-public-jwt"))
    upstream = PublicCafeApiClient(
        "https://level.example.com",
        transport=httpx.MockTransport(lambda _request: httpx.Response(404)),
    )
    test_app = create_app(settings=settings, public_api_client=upstream)

    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test",
    ) as client:
        missing = await client.get("/api/v1/public/cafe-collection/catalog")
        invalid = await client.get(
            "/api/v1/public/cafe-collection/catalog",
            headers={"Authorization": "Bearer wrong"},
        )
        authorized = await client.get(
            "/api/v1/public/cafe-collection/catalog",
            headers={"Authorization": "Bearer shared-public-jwt"},
        )
        image = await client.get("/api/v1/public/cafe-collection/cards/spent-tea/image")
    await upstream.close()

    assert missing.status_code == 401
    assert missing.json() == {"detail": "Invalid API key"}
    assert invalid.status_code == 401
    assert authorized.status_code == 404
    assert image.status_code == 200
