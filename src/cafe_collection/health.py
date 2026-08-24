"""Health, image, and website-facing Cafe Collection API."""

from __future__ import annotations

import hmac
from collections.abc import Awaitable, Callable

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from cafe_collection import assets
from cafe_collection.assets import card_image_path
from cafe_collection.config import ApiSettings
from cafe_collection.public_api import PublicCafeApiClient, PublicCafeApiUnavailable

PUBLIC_CAFE_API_PREFIX = "/api/v1/public/cafe-collection"
_FORWARDED_HEADERS = ("cache-control", "content-type", "etag", "last-modified")


def _verify_site_api_token(authorization: str | None, expected: str) -> bool:
    if not authorization or not expected:
        return False
    scheme, _, token = authorization.partition(" ")
    return (
        scheme.lower() == "bearer"
        and bool(token.strip())
        and hmac.compare_digest(token.strip(), expected)
    )


def _requires_site_api_token(path: str) -> bool:
    return path == f"{PUBLIC_CAFE_API_PREFIX}/catalog" or path.startswith(
        f"{PUBLIC_CAFE_API_PREFIX}/guilds/"
    )


def _upstream_response(upstream: httpx.Response) -> Response:
    headers = {
        name: upstream.headers[name]
        for name in _FORWARDED_HEADERS
        if name in upstream.headers
    }
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=headers,
    )


def create_app(
    *,
    settings: ApiSettings | None = None,
    public_api_client: PublicCafeApiClient | None = None,
) -> FastAPI:
    """Build the API, allowing an isolated upstream in contract tests."""
    api_settings = settings or ApiSettings()
    upstream = public_api_client or PublicCafeApiClient(
        api_settings.level_bot_api_base_url
    )
    application = FastAPI(
        title="Cafe Collection API",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=api_settings.allowed_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "OPTIONS"],
        allow_headers=["*"],
    )

    @application.middleware("http")
    async def require_site_api_token(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        path = request.url.path
        if _requires_site_api_token(path) and request.method != "OPTIONS":
            expected = api_settings.external_api_key.get_secret_value()
            if not _verify_site_api_token(
                request.headers.get("Authorization"),
                expected,
            ):
                return JSONResponse({"detail": "Invalid API key"}, status_code=401)
        return await call_next(request)

    @application.get("/healthz")
    async def healthz() -> dict[str, str]:
        """Process liveness; does not depend on external services."""
        return {"status": "ok"}

    @application.get("/readyz")
    async def readyz() -> dict[str, str]:
        """Deployment readiness for the locally served immutable image bundle."""
        if not assets.asset_bundle_ready():
            raise HTTPException(status_code=503, detail="image bundle unavailable")
        return {"status": "ready"}

    async def proxy(path: str) -> Response:
        try:
            response = await upstream.get(f"{PUBLIC_CAFE_API_PREFIX}{path}")
        except PublicCafeApiUnavailable as exc:
            raise HTTPException(
                status_code=502,
                detail="level-bot Cafe Collection API unavailable",
            ) from exc
        return _upstream_response(response)

    @application.get(f"{PUBLIC_CAFE_API_PREFIX}/catalog", response_model=None)
    async def catalog() -> Response:
        return await proxy("/catalog")

    @application.get(
        f"{PUBLIC_CAFE_API_PREFIX}/guilds/{{guild_id}}/leaderboards",
        response_model=None,
    )
    async def leaderboards(guild_id: str) -> Response:
        return await proxy(f"/guilds/{guild_id}/leaderboards")

    @application.get(
        f"{PUBLIC_CAFE_API_PREFIX}/guilds/{{guild_id}}/profiles/{{profile_id}}",
        response_model=None,
    )
    async def collection_profile(guild_id: str, profile_id: str) -> Response:
        return await proxy(f"/guilds/{guild_id}/profiles/{profile_id}")

    @application.get(
        f"{PUBLIC_CAFE_API_PREFIX}/cards/{{card_key}}/image",
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

    async def close_upstream() -> None:
        await upstream.close()

    application.add_event_handler("shutdown", close_upstream)
    return application


app = create_app()
