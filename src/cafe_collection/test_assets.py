from PIL import Image

from cafe_collection.assets import (
    ASSET_DIR,
    asset_bundle_ready,
    card_image_path,
    manifest,
    manifest_sha256,
)

NEW_CIVILIZATION_IMAGE_NAMES = {
    "uruk-barley-flatbread.jpg",
    "reed-straw-barley-beer.jpg",
    "date-syrup-sesame-sweets.jpg",
    "tigris-pomegranate-water.jpg",
    "twice-baked-malt-honey-rusks.jpg",
    "babylon-date-malt-drink.jpg",
    "clay-tablet-lamb-beet-stew.jpg",
    "ur-golden-straw-barley-beer.jpg",
    "ishtar-gate-lapis-cake.jpg",
    "ziggurat-stargazer-cordial.jpg",
    "harappa-wheat-barley-porridge.jpg",
    "painted-pottery-millet-water.jpg",
    "sesame-jujube-grain-cakes.jpg",
    "mohenjo-daro-cool-milk.jpg",
    "indus-pulse-barley-claypot.jpg",
    "harappa-melon-grape-cordial.jpg",
    "unicorn-seal-sesame-cake.jpg",
    "great-bath-jade-milk.jpg",
    "mohenjo-daro-brick-city-cake.jpg",
    "indus-seal-starlight-cordial.jpg",
    "yellow-river-millet-porridge.jpg",
    "painted-pottery-millet-drink.jpg",
    "stone-ground-millet-steamed-cakes.jpg",
    "jiahu-rice-honey-fruit-brew.jpg",
    "bronze-ding-herb-meat-stew.jpg",
    "anyang-herbal-millet-wine.jpg",
    "jade-bi-honey-cake.jpg",
    "oracle-bone-flower-rice-wine.jpg",
    "nine-ding-jade-grain-cake.jpg",
    "celestial-bronze-jue-cordial.jpg",
}


def test_bundled_assets_match_shared_manifest() -> None:
    data = manifest()

    assert data["version"] == 1
    assert len(data["files"]) == 495
    assert len(manifest_sha256()) == 64
    assert asset_bundle_ready() is True
    assert card_image_path("spent-tea") == ASSET_DIR / "spent-tea.jpg"
    assert card_image_path("../manifest") is None


def test_new_civilization_images_match_existing_card_dimensions() -> None:
    for image_name in NEW_CIVILIZATION_IMAGE_NAMES:
        with Image.open(ASSET_DIR / image_name) as image:
            assert image.format == "JPEG"
            assert image.size == (768, 768)
