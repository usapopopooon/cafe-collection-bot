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

MODERN_COFFEEHOUSE_IMAGE_NAMES = {
    "vanilla-cake-pop.jpg",
    "caramel-ribbon-macchiato.jpg",
    "white-chocolate-mocha.jpg",
    "new-york-cheesecake.jpg",
    "dark-chocolate-chip-frappe.jpg",
    "matcha-cream-frappe.jpg",
    "strawberry-cream-frappe.jpg",
    "red-velvet-cake.jpg",
}

COMPLIMENTARY_IMAGE_NAMES = {
    "register-candy.jpg",
    "free-bread-crusts.jpg",
    "sample-bite-rusk.jpg",
    "coffee-side-bean-snack.jpg",
    "leftover-dough-mini-cookie.jpg",
    "cake-shop-sponge-offcuts.jpg",
    "storefront-sample-cup.jpg",
}

ANCIENT_JAPANESE_ERA_IMAGE_NAMES = {
    "jomon-pottery-nut-soup.jpg",
    "yayoi-jar-red-rice-porridge.jpg",
    "kofun-keyhole-tomb-cake.jpg",
}

SOVIET_SHORTAGE_IMAGE_NAMES = {
    "black-bread-sunflower-oil.jpg",
    "sugared-macaroni.jpg",
    "thin-cabbage-canteen-soup.jpg",
    "thursday-fish-cutlet.jpg",
    "tomato-sprat-black-bread.jpg",
    "scrap-kartoshka-cake.jpg",
}

READY_MEAL_IMAGE_NAMES = {
    "erbswurst.jpg",
    "boston-brown-bread.jpg",
    "tv-dinner.jpg",
    "tinned-pie.jpg",
}

EUROPEAN_LOCAL_DRINK_IMAGE_NAMES = {
    "greek-frappe.jpg",
    "cafe-asiatico.jpg",
    "horchata-de-chufa.jpg",
    "diabolo-menthe.jpg",
    "salep.jpg",
    "cedevita.jpg",
}

LATIN_AMERICAN_LOCAL_DRINK_IMAGE_NAMES = {
    "chicha-morada.jpg",
    "agua-de-jamaica.jpg",
    "limonada-de-coco.jpg",
    "cajuina.jpg",
    "pinolillo.jpg",
    "mocochinchi.jpg",
}

AGE_OF_SAIL_PROVISION_IMAGE_NAMES = {
    "under-soaked-salt-beef.jpg",
    "salt-pork-pease-soup.jpg",
    "ships-hold-dried-cod.jpg",
    "hardened-voyage-cheese.jpg",
    "barrel-bottom-ale.jpg",
}

FIVE_NEW_SERIES_IMAGE_NAMES = {
    "night-train-paper-cup-coffee.jpg",
    "waiting-room-aluminum-teapot-tea.jpg",
    "dry-trolley-sandwich.jpg",
    "dining-car-consomme.jpg",
    "sleeper-train-breakfast-toast.jpg",
    "dining-car-beef-stew.jpg",
    "first-class-silver-breakfast.jpg",
    "school-lunch-milmake.jpg",
    "school-lunch-frozen-mandarin.jpg",
    "school-lunch-soft-noodles.jpg",
    "school-lunch-fried-bread.jpg",
    "depression-water-pie.jpg",
    "depression-mock-apple-pie.jpg",
    "hoover-stew.jpg",
    "soda-fountain-malted-milk.jpg",
    "soda-fountain-egg-cream.jpg",
    "soda-fountain-phosphate-soda.jpg",
    "polar-pemmican.jpg",
    "polar-condensed-milk-tea.jpg",
    "polar-compressed-soup.jpg",
    "polar-frozen-biscuits.jpg",
}

FOUR_EVERYDAY_PLACE_IMAGE_NAMES = {
    "vending-paper-cup-coffee.jpg",
    "vending-glass-bottle-cola.jpg",
    "vending-tempura-udon.jpg",
    "vending-boxed-hamburger.jpg",
    "vending-cup-noodles.jpg",
    "vending-ham-cheese-toast.jpg",
    "bathhouse-coffee-milk.jpg",
    "bathhouse-fruit-milk.jpg",
    "bathhouse-ramune.jpg",
    "bathhouse-ice-bar.jpg",
    "cinema-paper-bag-popcorn.jpg",
    "cinema-melted-ice-cola.jpg",
    "cinema-set-nachos.jpg",
    "cinema-last-hot-dog.jpg",
    "break-room-stick-coffee.jpg",
    "break-room-vending-corn-soup.jpg",
    "break-room-late-night-cup-noodles.jpg",
    "break-room-gift-manju.jpg",
    "break-room-named-pudding.jpg",
}

TRANSFER_STOP_IMAGE_NAMES = {
    "bus-center-yellow-curry.jpg",
    "platform-dashi-chuka-soba.jpg",
    "giant-karaage-soba.jpg",
    "sweet-savory-kashiwa-udon.jpg",
    "pre-departure-flat-udon.jpg",
    "station-tricolor-kashiwa-meshi.jpg",
}


EUROPEAN_BRAND_AND_PANTRY_IMAGE_NAMES = {
    "kofola.jpg",
    "cockta.jpg",
    "almdudler.jpg",
    "rivella.jpg",
    "kinnie.jpg",
    "irn-bru.jpg",
    "paulaner-spezi.jpg",
    "club-mate.jpg",
    "bionade-elderberry.jpg",
    "crodino.jpg",
    "sanbitter-rosso.jpg",
    "sanpellegrino-chinotto.jpg",
    "pommac.jpg",
    "apotekarnes-julmust.jpg",
    "vimto.jpg",
    "fentimans-dandelion-burdock.jpg",
    "brisa-maracuja.jpg",
    "chocomel.jpg",
    "fristi.jpg",
    "cacolac.jpg",
    "vinea.jpg",
    "traubisoda.jpg",
    "hellena-oranzada.jpg",
    "tymbark-apple-mint.jpg",
    "kubus-apple-carrot-peach.jpg",
    "pipi.jpg",
    "brifcor.jpg",
    "zhyvchyk.jpg",
    "baikal.jpg",
    "bread-kvass.jpg",
    "uzvar.jpg",
    "socata.jpg",
    "ryazhenka.jpg",
    "kama-kefir.jpg",
    "sbiten.jpg",
}


def test_european_brand_and_pantry_images_match_existing_card_dimensions() -> None:
    assert len(EUROPEAN_BRAND_AND_PANTRY_IMAGE_NAMES) == 35
    for image_name in EUROPEAN_BRAND_AND_PANTRY_IMAGE_NAMES:
        with Image.open(ASSET_DIR / image_name) as image:
            assert image.format == "JPEG"
            assert image.size == (768, 768)


def test_bundled_assets_match_shared_manifest() -> None:
    data = manifest()

    assert data["version"] == 1
    assert len(data["files"]) == 621
    assert len(manifest_sha256()) == 64
    assert asset_bundle_ready() is True
    assert card_image_path("spent-tea") == ASSET_DIR / "spent-tea.jpg"
    assert card_image_path("../manifest") is None


def test_new_civilization_images_match_existing_card_dimensions() -> None:
    for image_name in NEW_CIVILIZATION_IMAGE_NAMES:
        with Image.open(ASSET_DIR / image_name) as image:
            assert image.format == "JPEG"
            assert image.size == (768, 768)


def test_modern_coffeehouse_images_match_existing_card_dimensions() -> None:
    for image_name in MODERN_COFFEEHOUSE_IMAGE_NAMES:
        with Image.open(ASSET_DIR / image_name) as image:
            assert image.format == "JPEG"
            assert image.size == (768, 768)


def test_complimentary_images_match_existing_card_dimensions() -> None:
    for image_name in COMPLIMENTARY_IMAGE_NAMES:
        with Image.open(ASSET_DIR / image_name) as image:
            assert image.format == "JPEG"
            assert image.size == (768, 768)


def test_ancient_japanese_era_images_match_existing_card_dimensions() -> None:
    for image_name in ANCIENT_JAPANESE_ERA_IMAGE_NAMES:
        with Image.open(ASSET_DIR / image_name) as image:
            assert image.format == "JPEG"
            assert image.size == (768, 768)


def test_soviet_shortage_images_match_existing_card_dimensions() -> None:
    for image_name in SOVIET_SHORTAGE_IMAGE_NAMES:
        with Image.open(ASSET_DIR / image_name) as image:
            assert image.format == "JPEG"
            assert image.size == (768, 768)


def test_ready_meal_images_match_existing_card_dimensions() -> None:
    for image_name in READY_MEAL_IMAGE_NAMES:
        with Image.open(ASSET_DIR / image_name) as image:
            assert image.format == "JPEG"
            assert image.size == (768, 768)


def test_european_local_drink_images_match_existing_card_dimensions() -> None:
    for image_name in EUROPEAN_LOCAL_DRINK_IMAGE_NAMES:
        with Image.open(ASSET_DIR / image_name) as image:
            assert image.format == "JPEG"
            assert image.size == (768, 768)


def test_latin_american_local_drink_images_match_existing_card_dimensions() -> None:
    for image_name in LATIN_AMERICAN_LOCAL_DRINK_IMAGE_NAMES:
        with Image.open(ASSET_DIR / image_name) as image:
            assert image.format == "JPEG"
            assert image.size == (768, 768)


def test_age_of_sail_provision_images_match_existing_card_dimensions() -> None:
    for image_name in AGE_OF_SAIL_PROVISION_IMAGE_NAMES:
        with Image.open(ASSET_DIR / image_name) as image:
            assert image.format == "JPEG"
            assert image.size == (768, 768)


def test_five_new_series_images_match_existing_card_dimensions() -> None:
    for image_name in FIVE_NEW_SERIES_IMAGE_NAMES:
        with Image.open(ASSET_DIR / image_name) as image:
            assert image.format == "JPEG"
            assert image.size == (768, 768)


def test_four_everyday_place_images_match_existing_card_dimensions() -> None:
    for image_name in FOUR_EVERYDAY_PLACE_IMAGE_NAMES:
        with Image.open(ASSET_DIR / image_name) as image:
            assert image.format == "JPEG"
            assert image.size == (768, 768)


def test_transfer_stop_images_match_existing_card_dimensions() -> None:
    for image_name in TRANSFER_STOP_IMAGE_NAMES:
        with Image.open(ASSET_DIR / image_name) as image:
            assert image.format == "JPEG"
            assert image.size == (768, 768)
