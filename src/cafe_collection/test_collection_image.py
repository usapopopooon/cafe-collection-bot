from cafe_collection.collection_image import render_collection_pages
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
