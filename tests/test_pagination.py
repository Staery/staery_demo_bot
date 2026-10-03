import pytest

from bot.services.pagination import paginate

ITEMS = list(range(1, 23))  # 22 items


def test_first_page() -> None:
    page = paginate(ITEMS, 0, 5)
    assert page.items == (1, 2, 3, 4, 5)
    assert (page.number, page.total_pages, page.total_items) == (0, 5, 22)
    assert not page.has_prev
    assert page.has_next


def test_last_page_is_partial() -> None:
    page = paginate(ITEMS, 4, 5)
    assert page.items == (21, 22)
    assert page.has_prev
    assert not page.has_next


@pytest.mark.parametrize(("requested", "expected"), [(-3, 0), (99, 4)])
def test_out_of_range_pages_are_clamped(requested: int, expected: int) -> None:
    assert paginate(ITEMS, requested, 5).number == expected


def test_empty_sequence_has_one_empty_page() -> None:
    page = paginate([], 0, 5)
    assert page.items == ()
    assert page.total_pages == 1
    assert not page.has_prev
    assert not page.has_next


def test_exact_multiple() -> None:
    assert paginate(list(range(10)), 1, 5).total_pages == 2


def test_invalid_page_size() -> None:
    with pytest.raises(ValueError, match="per_page"):
        paginate(ITEMS, 0, 0)
