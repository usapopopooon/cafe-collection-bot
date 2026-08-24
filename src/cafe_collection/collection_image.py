"""Render one rarity of the remotely owned collection using local assets."""

from __future__ import annotations

from collections.abc import Sequence
from io import BytesIO

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

from cafe_collection.assets import ASSET_DIR, card_image_path
from cafe_collection.level_api import CafeCollectionCard

CELL_SIZE = 160
COLUMNS = 5
ROWS = 8
RARITY_LABELS = {"C": "N", "UC": "HN", "MYTHIC": "幻"}


def _render_page(cards: Sequence[CafeCollectionCard]) -> bytes:
    columns = max(1, min(COLUMNS, len(cards)))
    rows = max(1, min(ROWS, (len(cards) + columns - 1) // columns))
    canvas = Image.new("RGB", (CELL_SIZE * columns, CELL_SIZE * rows), "#251a16")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default(size=18)
    with Image.open(ASSET_DIR / "card-back.jpg") as source:
        card_back = source.convert("RGB")
    for index in range(columns * rows):
        x = index % columns * CELL_SIZE
        y = index // columns * CELL_SIZE
        if index >= len(cards):
            draw.rectangle(
                (x + 3, y + 3, x + CELL_SIZE - 3, y + CELL_SIZE - 3),
                outline="#4a342a",
                width=2,
            )
            continue
        card = cards[index]
        count = max(0, card.count)
        if count:
            image_path = card_image_path(card.key)
            if image_path is None or image_path.name != card.image_filename:
                raise ValueError(f"invalid Cafe image mapping: {card.key}")
            with Image.open(image_path) as source:
                image = source.convert("RGB")
        else:
            image = card_back.copy()
        tile = ImageOps.fit(image, (CELL_SIZE, CELL_SIZE))
        if not count:
            tile = ImageEnhance.Brightness(tile).enhance(0.38)
        canvas.paste(tile, (x, y))
        draw.rectangle((x + 4, y + 4, x + 58, y + 32), fill="#17100dcc")
        draw.text(
            (x + 10, y + 8),
            RARITY_LABELS.get(card.rarity, card.rarity),
            font=font,
            fill="white",
        )
        badge = "-" if count == 0 else f"x{count}"
        draw.rectangle(
            (
                x + CELL_SIZE - 58,
                y + CELL_SIZE - 34,
                x + CELL_SIZE - 4,
                y + CELL_SIZE - 4,
            ),
            fill="#17100dcc",
        )
        draw.text(
            (x + CELL_SIZE - 51, y + CELL_SIZE - 30),
            badge,
            font=font,
            fill="white",
        )
    output = BytesIO()
    canvas.save(output, format="JPEG", quality=88, optimize=True)
    return output.getvalue()


def render_collection_pages(cards: Sequence[CafeCollectionCard]) -> tuple[bytes, ...]:
    """Render at most two Discord-sized pages for one rarity."""
    page_size = COLUMNS * ROWS
    return tuple(
        _render_page(cards[start : start + page_size])
        for start in range(0, len(cards), page_size)
    )
