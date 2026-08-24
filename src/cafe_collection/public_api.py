"""Read-only client for level-bot's public Cafe Collection data."""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx


class PublicCafeApiUnavailable(RuntimeError):
    """Raised when the authoritative level-bot API cannot be reached."""


@dataclass
class PublicCafeApiClient:
    """Fetch public Cafe data without duplicating level-bot's database."""

    base_url: str
    transport: httpx.AsyncBaseTransport | None = field(default=None, repr=False)
    _client: httpx.AsyncClient = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=self.base_url.rstrip("/"),
            headers={"Accept": "application/json"},
            timeout=httpx.Timeout(10.0),
            transport=self.transport,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def get(self, path: str) -> httpx.Response:
        try:
            return await self._client.get(path)
        except httpx.HTTPError as exc:
            raise PublicCafeApiUnavailable from exc
