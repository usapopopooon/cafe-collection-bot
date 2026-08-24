"""Health and image API for Coolify and Cafe clients."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from cafe_collection import assets
from cafe_collection.assets import card_image_path

app = FastAPI(
    title="Cafe Collection API",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    """Process liveness; does not depend on external services."""
    return {"status": "ok"}


@app.get("/readyz")
async def readyz() -> dict[str, str]:
    """Deployment readiness for the locally served immutable image bundle."""
    if not assets.asset_bundle_ready():
        raise HTTPException(status_code=503, detail="image bundle unavailable")
    return {"status": "ready"}


@app.get(
    "/api/v1/public/cafe-collection/cards/{card_key}/image",
    response_class=FileResponse,
)
async def card_image(card_key: str) -> FileResponse:
    """Serve the same immutable card JPEG bundle as level-bot."""
    path = card_image_path(card_key)
    if path is None:
        raise HTTPException(status_code=404, detail="Card not found")
    return FileResponse(
        path,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
