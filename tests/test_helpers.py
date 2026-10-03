"""Small pure helpers: callback data, deep links, formatting, catalogue, payments, keyboards."""

import re
from datetime import timedelta

import pytest

from bot.handlers.payments import make_payload, parse_payload
from bot.keyboards import inline, reply
from bot.keyboards.callbacks import pack, pattern, unpack
from bot.services import catalog
from bot.services.deep_links import (
    PayloadKind,
    StartPayload,
    feedback_link,
    item_link,
    parse_start_payload,
    referral_link,
)
from bot.services.formatting import haversine_km, human_size, to_seconds
from bot.services.pagination import paginate


def test_callback_pack_and_unpack() -> None:
    data = pack("catalog", "item", 5, 2)
    assert data == "catalog:item:5:2"
    assert unpack(data) == ["catalog", "item", "5", "2"]
    assert unpack(None) == []


def test_callback_data_limit() -> None:
    with pytest.raises(ValueError, match="64 bytes"):
        pack("x" * 70)


def test_callback_pattern() -> None:
    regex = re.compile(pattern("catalog"))
    assert regex.match("catalog:page:1")
    assert regex.match("catalog")
    assert not regex.match("catalogue:page:1")
    assert re.match(pattern("reminder", "del"), "reminder:del:3")
    assert not re.match(pattern("reminder", "del"), "reminder:snooze:3")


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (None, StartPayload(PayloadKind.NONE)),
        ([], StartPayload(PayloadKind.NONE)),
        (["ref_42"], StartPayload(PayloadKind.REFERRAL, 42, "ref_42")),
        (["item_7"], StartPayload(PayloadKind.ITEM, 7, "item_7")),
        (["feedback"], StartPayload(PayloadKind.FEEDBACK, raw="feedback")),
        (["ref_abc"], StartPayload(PayloadKind.UNKNOWN, raw="ref_abc")),
        (["inline"], StartPayload(PayloadKind.UNKNOWN, raw="inline")),
    ],
)
def test_parse_start_payload(args: list[str] | None, expected: StartPayload) -> None:
    assert parse_start_payload(args) == expected


def test_deep_links() -> None:
    assert referral_link("demo_bot", 42) == "https://t.me/demo_bot?start=ref_42"
    assert item_link("demo_bot", 3) == "https://t.me/demo_bot?start=item_3"
    assert feedback_link("demo_bot") == "https://t.me/demo_bot?start=feedback"


@pytest.mark.parametrize(
    ("size", "expected"),
    [(None, "?"), (0, "0 B"), (1023, "1023 B"), (1536, "1.5 KB"), (5 * 1024**2, "5.0 MB"),
     (3 * 1024**4, "3072.0 GB")],
)  # fmt: skip
def test_human_size(size: int | None, expected: str) -> None:
    assert human_size(size) == expected


def test_haversine() -> None:
    paris, london = (48.8566, 2.3522), (51.5074, -0.1278)
    assert haversine_km(*paris, *paris) == pytest.approx(0)
    assert haversine_km(*paris, *london) == pytest.approx(343.5, abs=1)


def test_to_seconds() -> None:
    assert to_seconds(timedelta(minutes=1)) == 60
    assert to_seconds(7) == 7
    assert to_seconds(None) == 0


def test_catalog_search() -> None:
    assert catalog.search("")[:1] == [catalog.ITEMS[0]]
    assert [item.name for item in catalog.search("PYTEST")] == ["pytest"]
    # name matches come before description matches
    results = catalog.search("sql")
    assert results[0].name == "SQLAlchemy"
    assert any(item.name == "aiosqlite" for item in results)
    assert catalog.search("асинхрон", lang="ru")
    assert catalog.search("zzz") == []
    assert catalog.get_item(1) is catalog.ITEMS[0]
    assert catalog.get_item(999) is None


def test_catalog_ids_are_unique() -> None:
    ids = [item.id for item in catalog.ITEMS]
    assert len(ids) == len(set(ids))


def test_payment_payload_roundtrip() -> None:
    assert parse_payload(make_payload(42, 10)) == (42, 10)
    for bad in ("", "donation:1", "other:1:2", "donation:x:2", "donation:1:2:3"):
        assert parse_payload(bad) is None


def test_catalog_keyboard_navigation() -> None:
    first = inline.catalog_page(paginate(catalog.ITEMS, 0, 5), "en").inline_keyboard
    assert len(first) == 6  # 5 items + navigation row
    assert [b.text for b in first[-1]] == ["1/5", "▶️"]
    last = inline.catalog_page(paginate(catalog.ITEMS, 4, 5), "en").inline_keyboard
    assert [b.callback_data for b in last[-1]] == ["catalog:page:3", "catalog:noop"]


def test_all_inline_buttons_fit_the_callback_limit() -> None:
    markups = [
        inline.main_menu("ru", "https://t.me/share/url?url=x"),
        inline.settings_menu("ru", None),
        inline.media_menu("ru"),
        inline.dice_menu(),
        inline.rating("ru"),
        inline.feedback_confirm("ru"),
        inline.donate_menu("ru"),
        inline.broadcast_confirm("ru"),
    ]
    for markup in markups:
        for row in markup.inline_keyboard:
            for button in row:
                if button.callback_data is not None:
                    assert len(str(button.callback_data).encode()) <= 64


@pytest.mark.parametrize("lang", ["en", "ru"])
def test_reply_buttons_match_their_filter(lang: str) -> None:
    keyboard = reply.main_menu(lang).keyboard
    labels = {button.text for row in keyboard for button in row}
    for key in ("btn.catalog", "btn.feedback", "btn.media", "btn.settings", "btn.help"):
        regex = re.compile(reply.button_regex(key))
        assert any(regex.match(label) for label in labels), key
    assert not re.match(reply.button_regex("btn.help"), "help me please")
