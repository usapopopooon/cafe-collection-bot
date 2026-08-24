import pytest
from httpx import ASGITransport, AsyncClient

from cafe_collection import assets
from cafe_collection.health import app


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
