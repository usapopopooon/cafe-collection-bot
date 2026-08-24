"""Internal health API for Coolify and future public Cafe routes."""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from sqlalchemy.exc import SQLAlchemyError

from cafe_collection import database
from cafe_collection.config import RuntimeSettings

logger = logging.getLogger(__name__)
app = FastAPI(
    title="Cafe Collection API",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    """Process liveness; does not depend on PostgreSQL."""
    return {"status": "ok"}


@app.get("/readyz")
async def readyz() -> dict[str, str]:
    """Deployment readiness including PostgreSQL connectivity."""
    settings = RuntimeSettings()
    try:
        await database.ping_database(settings.database_url)
    except SQLAlchemyError as exc:
        logger.warning("Database readiness check failed: %s", exc)
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return {"status": "ready"}
