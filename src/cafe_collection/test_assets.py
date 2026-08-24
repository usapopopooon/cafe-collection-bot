from cafe_collection.assets import (
    ASSET_DIR,
    asset_bundle_ready,
    card_image_path,
    manifest,
    manifest_sha256,
)


def test_bundled_assets_match_shared_manifest() -> None:
    data = manifest()

    assert data["version"] == 1
    assert len(data["files"]) == 363
    assert len(manifest_sha256()) == 64
    assert asset_bundle_ready() is True
    assert card_image_path("spent-tea") == ASSET_DIR / "spent-tea.jpg"
    assert card_image_path("../manifest") is None
