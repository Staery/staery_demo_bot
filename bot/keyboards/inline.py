"""Inline keyboards (buttons attached to a message)."""

from __future__ import annotations

from collections.abc import Sequence

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import DiceEmoji

from bot.i18n import t
from bot.keyboards.callbacks import pack
from bot.services.catalog import CatalogItem
from bot.services.pagination import Page
from bot.storage import ReminderRecord

LANGUAGE_FLAGS = {"en": "🇬🇧 English", "ru": "🇷🇺 Русский"}
DONATION_AMOUNTS = (1, 10, 50)


def main_menu(lang: str, share_url: str | None = None) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(t("btn.catalog", lang), callback_data=pack("catalog", "page", 0)),
            InlineKeyboardButton(t("btn.feedback", lang), callback_data=pack("feedback", "start")),
        ],
        [
            InlineKeyboardButton(t("btn.media", lang), callback_data=pack("media", "menu")),
            InlineKeyboardButton(t("btn.settings", lang), callback_data=pack("settings", "open")),
        ],
        [
            InlineKeyboardButton(t("btn.inline", lang), switch_inline_query_current_chat=""),
            InlineKeyboardButton(t("btn.donate", lang), callback_data=pack("donate", "menu")),
        ],
    ]
    if share_url:
        rows.append([InlineKeyboardButton(t("btn.invite", lang), url=share_url)])
    return InlineKeyboardMarkup(rows)


def settings_menu(lang: str, chosen: str | None) -> InlineKeyboardMarkup:
    def mark(code: str | None, label: str) -> str:
        return f"✅ {label}" if code == chosen else label

    buttons = [
        InlineKeyboardButton(mark(code, label), callback_data=pack("settings", "lang", code))
        for code, label in LANGUAGE_FLAGS.items()
    ]
    auto = InlineKeyboardButton(
        mark(None, t("settings.auto", lang)), callback_data=pack("settings", "lang", "auto")
    )
    return InlineKeyboardMarkup([buttons, [auto]])


def catalog_page(page: Page[CatalogItem], lang: str) -> InlineKeyboardMarkup:
    """One button per item plus a ``◀️ 2/5 ▶️`` navigation row."""
    rows = [
        [
            InlineKeyboardButton(
                f"{item.emoji} {item.name}",
                callback_data=pack("catalog", "item", item.id, page.number),
            )
        ]
        for item in page.items
    ]
    nav: list[InlineKeyboardButton] = []
    if page.has_prev:
        nav.append(
            InlineKeyboardButton("◀️", callback_data=pack("catalog", "page", page.number - 1))
        )
    nav.append(
        InlineKeyboardButton(
            f"{page.number + 1}/{page.total_pages}", callback_data=pack("catalog", "noop")
        )
    )
    if page.has_next:
        nav.append(
            InlineKeyboardButton("▶️", callback_data=pack("catalog", "page", page.number + 1))
        )
    rows.append(nav)
    return InlineKeyboardMarkup(rows)


def catalog_item(item: CatalogItem, back_page: int, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(t("catalog.open_site", lang), url=item.url)],
            [InlineKeyboardButton(t("catalog.share", lang), switch_inline_query=item.name)],
            [
                InlineKeyboardButton(
                    t("catalog.back", lang), callback_data=pack("catalog", "page", back_page)
                )
            ],
        ]
    )


def rating(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("⭐" * value, callback_data=pack("feedback", "rate", value))
                for value in range(1, 4)
            ],
            [
                InlineKeyboardButton("⭐" * value, callback_data=pack("feedback", "rate", value))
                for value in range(4, 6)
            ],
        ]
    )


def feedback_confirm(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    t("feedback.send", lang), callback_data=pack("feedback", "send")
                )
            ],
            [
                InlineKeyboardButton(
                    t("feedback.restart", lang), callback_data=pack("feedback", "restart")
                ),
                InlineKeyboardButton(
                    t("btn.cancel", lang), callback_data=pack("feedback", "cancel")
                ),
            ],
        ]
    )


def media_menu(lang: str) -> InlineKeyboardMarkup:
    kinds = ("photo", "album", "document", "location", "venue", "contact", "poll", "quiz")
    buttons = [
        InlineKeyboardButton(t(f"media.kind.{kind}", lang), callback_data=pack("media", kind))
        for kind in kinds
    ]
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    rows.append(
        [InlineKeyboardButton(t("media.kind.dice", lang), callback_data=pack("dice", "menu"))]
    )
    return InlineKeyboardMarkup(rows)


def another_photo(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(t("media.another", lang), callback_data=pack("media", "next"))]]
    )


def dice_menu() -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(emoji.value, callback_data=pack("dice", emoji.name))
        for emoji in DiceEmoji
    ]
    return InlineKeyboardMarkup([buttons[:3], buttons[3:]])


def reminders_list(reminders: Sequence[ReminderRecord]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"❌ #{reminder.id} {reminder.text[:30]}",
                    callback_data=pack("reminder", "del", reminder.id),
                )
            ]
            for reminder in reminders
        ]
    )


def reminder_snooze(reminder_id: int, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    t("reminders.snooze", lang),
                    callback_data=pack("reminder", "snooze", reminder_id),
                )
            ]
        ]
    )


def broadcast_confirm(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    t("admin.broadcast_send", lang), callback_data=pack("broadcast", "send")
                ),
                InlineKeyboardButton(
                    t("btn.cancel", lang), callback_data=pack("broadcast", "cancel")
                ),
            ]
        ]
    )


def donate_menu(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(f"⭐ {amount}", callback_data=pack("donate", amount))
                for amount in DONATION_AMOUNTS
            ]
        ]
    )
