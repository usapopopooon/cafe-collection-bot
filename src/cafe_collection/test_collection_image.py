from collections.abc import Sequence

import pytest

from cafe_collection import collection_image
from cafe_collection.collection_image import (
    PAGE_SIZE,
    render_collection_page,
    render_collection_pages,
)
from cafe_collection.level_api import CafeCollectionCard


def _card(index: int, *, count: int) -> CafeCollectionCard:
    return CafeCollectionCard(
        key="spent-tea",
        name=f"カード{index}",
        rarity="C",
        description="説明",
        image_filename="spent-tea.jpg",
        count=count,
        redeemable_count=max(0, count - 1),
        lifetime_count=count,
        is_protected=False,
    )


def test_collection_renderer_pages_and_hides_unowned_cards() -> None:
    pages = render_collection_pages(
        [_card(index, count=1 if index == 0 else 0) for index in range(41)]
    )

    assert len(pages) == 2
    assert all(page.startswith(b"\xff\xd8\xff") for page in pages)


def test_collection_renderer_only_opens_requested_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cards = [_card(index, count=1) for index in range(PAGE_SIZE * 25 + 1)]
    rendered: list[list[CafeCollectionCard]] = []

    def render(page_cards: Sequence[CafeCollectionCard]) -> bytes:
        rendered.append(list(page_cards))
        return b"image"

    monkeypatch.setattr(collection_image, "_render_page", render)

    assert render_collection_page(cards, 25) == b"image"
    assert rendered == [[cards[-1]]]
    with pytest.raises(IndexError):
        render_collection_page(cards, 26)
