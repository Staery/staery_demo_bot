"""Generic, Telegram-independent pagination."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Page(Generic[T]):
    items: tuple[T, ...]
    number: int  # zero-based
    total_pages: int
    total_items: int

    @property
    def has_prev(self) -> bool:
        return self.number > 0

    @property
    def has_next(self) -> bool:
        return self.number < self.total_pages - 1


def paginate(items: Sequence[T], page: int, per_page: int) -> Page[T]:
    """Return page ``page`` (zero-based). Out-of-range page numbers are clamped."""
    if per_page < 1:
        raise ValueError("per_page must be >= 1")
    total_pages = max(1, math.ceil(len(items) / per_page))
    number = min(max(page, 0), total_pages - 1)
    start = number * per_page
    return Page(
        items=tuple(items[start : start + per_page]),
        number=number,
        total_pages=total_pages,
        total_items=len(items),
    )
