"""Reply keyboards (the custom keyboard that replaces the phone keyboard)."""

from __future__ import annotations

import re

from telegram import KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import filters

from bot.i18n import i18n, t


def main_menu(lang: str) -> ReplyKeyboardMarkup:
    """Persistent main menu. Two buttons ask Telegram to share the location / contact."""
    return ReplyKeyboardMarkup(
        [
            [t("btn.catalog", lang), t("btn.feedback", lang)],
            [t("btn.media", lang), t("btn.settings", lang)],
            [
                KeyboardButton(t("btn.location", lang), request_location=True),
                KeyboardButton(t("btn.contact", lang), request_contact=True),
            ],
            [t("btn.help", lang)],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder=t("menu.placeholder", lang),
    )


def cancel_keyboard(lang: str, *extra_rows: list[str]) -> ReplyKeyboardMarkup:
    """One-time keyboard used inside the feedback conversation."""
    return ReplyKeyboardMarkup(
        [*extra_rows, [t("btn.cancel", lang)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def button_regex(key: str) -> str:
    """Regex matching the label of button ``key`` in every supported language."""
    options = "|".join(re.escape(label) for label in i18n.variants(key))
    return rf"^(?:{options})$"


def button_filter(key: str) -> filters.MessageFilter:
    """``filters.Regex`` for a localised reply-keyboard button."""
    return filters.Regex(button_regex(key))
