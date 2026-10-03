from datetime import timedelta

import pytest

from bot.services.durations import (
    DurationError,
    format_duration,
    parse_duration,
    parse_reminder_args,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("10m", timedelta(minutes=10)),
        ("90s", timedelta(seconds=90)),
        ("1h30m", timedelta(hours=1, minutes=30)),
        ("1h 30m", timedelta(hours=1, minutes=30)),
        ("2d", timedelta(days=2)),
        ("1w", timedelta(weeks=1)),
        ("15", timedelta(minutes=15)),
        ("5 min", timedelta(minutes=5)),
        ("2 hours", timedelta(hours=2)),
        ("10мин", timedelta(minutes=10)),
        ("1ч 15м", timedelta(hours=1, minutes=15)),
        ("3д", timedelta(days=3)),
        ("  45S ", timedelta(seconds=45)),
    ],
)
def test_parse_duration(text: str, expected: timedelta) -> None:
    assert parse_duration(text) == expected


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("", "invalid"),
        ("abc", "invalid"),
        ("10x", "invalid"),
        ("m10", "invalid"),
        ("1h-30m", "invalid"),
        ("0m", "too_short"),
        ("31d", "too_long"),
    ],
)
def test_parse_duration_errors(text: str, code: str) -> None:
    with pytest.raises(DurationError) as exc_info:
        parse_duration(text)
    assert exc_info.value.code == code


@pytest.mark.parametrize(
    ("args", "delay", "text"),
    [
        (["10m", "drink", "water"], timedelta(minutes=10), "drink water"),
        (["1h", "30m", "call", "mom"], timedelta(hours=1, minutes=30), "call mom"),
        (["10", "мин", "позвонить"], timedelta(minutes=10), "позвонить"),
        (["10", "tea"], timedelta(minutes=10), "tea"),
        (["10m", "2nd", "meeting"], timedelta(minutes=10), "2nd meeting"),
        (["1h", "30", "push-ups"], timedelta(hours=1), "30 push-ups"),
    ],
)
def test_parse_reminder_args(args: list[str], delay: timedelta, text: str) -> None:
    assert parse_reminder_args(args) == (delay, text)


@pytest.mark.parametrize(
    ("args", "code"),
    [
        ([], "invalid"),
        (["tomorrow", "tea"], "invalid"),
        (["10m"], "no_text"),
        (["10m", "x" * 501], "text_too_long"),
        (["40d", "tea"], "too_long"),
    ],
)
def test_parse_reminder_args_errors(args: list[str], code: str) -> None:
    with pytest.raises(DurationError) as exc_info:
        parse_reminder_args(args)
    assert exc_info.value.code == code


@pytest.mark.parametrize(
    ("value", "lang", "expected"),
    [
        (timedelta(hours=1, minutes=30), "en", "1h 30m"),
        (timedelta(hours=1, minutes=30), "ru", "1ч 30мин"),
        (timedelta(days=2, seconds=5), "en", "2d 5s"),
        (timedelta(0), "en", "0s"),
        (timedelta(seconds=-5), "ru", "0с"),
        (timedelta(minutes=10), "de", "10m"),
    ],
)
def test_format_duration(value: timedelta, lang: str, expected: str) -> None:
    assert format_duration(value, lang) == expected
