"""Minimal database readiness boundary for the deployable shell."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def ping_database(database_url: str) -> None:
    """Open a short-lived connection and verify PostgreSQL answers."""
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    finally:
        await engine.dispose()
