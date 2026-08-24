"""Immutable Cafe image bundle shared with level-bot."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TypedDict, cast

ASSET_DIR = Path(__file__).parent / "assets"
MANIFEST_PATH = ASSET_DIR / "manifest.json"


class AssetEntry(TypedDict):
    sha256: str
    size: int


class AssetManifest(TypedDict):
    version: int
    files: dict[str, AssetEntry]


def manifest() -> AssetManifest:
    """Load the checked-in manifest for the bundled JPEG files."""
    return cast(
        AssetManifest,
        json.loads(MANIFEST_PATH.read_text(encoding="utf-8")),
    )


def manifest_sha256() -> str:
    """Return the version identity exchanged with level-bot."""
    return hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()


def asset_bundle_ready() -> bool:
    """Return whether every manifest entry exists with its pinned size."""
    try:
        entries = manifest()["files"]
        bundled_names = {path.name for path in ASSET_DIR.glob("*.jpg")}
        if bundled_names != set(entries):
            return False
        return all(
            (ASSET_DIR / filename).stat().st_size == entry["size"]
            for filename, entry in entries.items()
        )
    except (AttributeError, KeyError, OSError, TypeError, ValueError):
        return False


def card_image_path(card_key: str) -> Path | None:
    """Resolve a card key without allowing arbitrary filesystem access."""
    filename = f"{card_key}.jpg"
    if filename not in manifest()["files"]:
        return None
    path = ASSET_DIR / filename
    return path if path.is_file() else None
