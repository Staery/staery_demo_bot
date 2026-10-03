"""Human-friendly durations for ``/remind``: ``10m``, ``1h30m``, ``2d``, ``45 сек``..."""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import timedelta

MAX_DURATION = timedelta(days=30)
MAX_REMINDER_TEXT = 500

_UNIT_SECONDS: dict[str, int] = {
    # English
    "s": 1, "sec": 1, "secs": 1, "second": 1, "seconds": 1,
    "m": 60, "min": 60, "mins": 60, "minute": 60, "minutes": 60,
    "h": 3600, "hr": 3600, "hrs": 3600, "hour": 3600, "hours": 3600,
    "d": 86400, "day": 86400, "days": 86400,
    "w": 604800, "week": 604800, "weeks": 604800,
    # Russian
    "с": 1, "сек": 1,
    "м": 60, "мин": 60,
    "ч": 3600, "час": 3600, "часа": 3600, "часов": 3600,
    "д": 86400, "дн": 86400, "день": 86400, "дня": 86400, "дней": 86400,
    "н": 604800, "нед": 604800,
}  # fmt: skip

_TOKEN_RE = re.compile(r"(\d+)([^\d\s]*)")

_LABELS = {
    "en": ("d", "h", "m", "s"),
    "ru": ("д", "ч", "мин", "с"),
}


class DurationError(ValueError):
    """Raised for unparsable or out-of-range durations. ``code`` is an i18n key suffix."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def parse_duration(text: str) -> timedelta:
    """Parse ``"1h30m"``, ``"1h 30m"``, ``"90s"``, ``"2д"``. A bare number means minutes."""
    compact = re.sub(r"\s+", "", text.lower())
    if not compact:
        raise DurationError("invalid")
    if compact.isdigit():
        compact += "m"

    position, seconds = 0, 0
    for match in _TOKEN_RE.finditer(compact):
        if match.start() != position:
            raise DurationError("invalid")
        amount, unit = match.groups()
        if unit not in _UNIT_SECONDS:
            raise DurationError("invalid")
        seconds += int(amount) * _UNIT_SECONDS[unit]
        position = match.end()
    if position != len(compact):
        raise DurationError("invalid")

    if seconds <= 0:
        raise DurationError("too_short")
    if seconds > MAX_DURATION.total_seconds():
        raise DurationError("too_long")
    return timedelta(seconds=seconds)


def _looks_like_duration(arg: str) -> bool:
    try:
        parse_duration(arg)
    except DurationError as exc:
        return exc.code == "too_long"
    return True


def _continues_duration(previous: str, arg: str) -> bool:
    """Does ``arg`` continue a duration? (``"30m"`` after ``"1h"``, ``"min"`` after ``"10"``)"""
    if previous.isdigit():
        return arg.lower() in _UNIT_SECONDS
    return not arg.isdigit() and _looks_like_duration(arg)


def parse_reminder_args(args: Sequence[str]) -> tuple[timedelta, str]:
    """Split ``/remind`` arguments into ``(duration, text)``.

    Leading arguments that look like durations are consumed:
    ``["1h", "30m", "call", "mom"]`` -> ``(1:30:00, "call mom")``.
    """
    if not args:
        raise DurationError("invalid")
    # The first argument is always treated as (part of) the duration, so that a typo there
    # is reported instead of silently becoming part of the reminder text.
    count = 1
    while count < len(args) and _continues_duration(args[count - 1], args[count]):
        count += 1
    duration = parse_duration("".join(args[:count]))
    text = " ".join(args[count:]).strip()
    if not text:
        raise DurationError("no_text")
    if len(text) > MAX_REMINDER_TEXT:
        raise DurationError("text_too_long")
    return duration, text


def format_duration(value: timedelta, lang: str = "en") -> str:
    """``timedelta(hours=1, minutes=30)`` -> ``"1h 30m"`` (or ``"1ч 30мин"``)."""
    labels = _LABELS.get(lang, _LABELS["en"])
    total = int(value.total_seconds())
    if total <= 0:
        return f"0{labels[3]}"
    parts = []
    for size, label in zip((86400, 3600, 60, 1), labels, strict=True):
        amount, total = divmod(total, size)
        if amount:
            parts.append(f"{amount}{label}")
    return " ".join(parts)
