from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import SQLAlchemyError

from cafe_collection import database
from cafe_collection.health import app


async def test_healthz_is_independent_of_database() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readyz_checks_database(monkeypatch: pytest.MonkeyPatch) -> None:
    ping = AsyncMock(return_value=None)
    monkeypatch.setattr(database, "ping_database", ping)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
    ping.assert_awaited_once()


async def test_readyz_returns_503_when_database_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        database,
        "ping_database",
        AsyncMock(side_effect=SQLAlchemyError("down")),
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/readyz")

    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable"}
