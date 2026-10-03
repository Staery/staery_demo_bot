"""Inline mode: type ``@<bot> text`` in any chat.

Inline mode must be switched on in @BotFather (``/setinline``).
"""

from __future__ import annotations

import hashlib
import html

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InlineQueryResultsButton,
    InputTextMessageContent,
    Update,
)
from telegram.ext import Application, InlineQueryHandler

from bot.context import BotContext
from bot.i18n import t
from bot.services import catalog
from bot.services.deep_links import item_link

MAX_QUERY_PREVIEW = 64


def _result_id(*parts: object) -> str:
    """Stable result id (max 64 bytes) so Telegram can cache identical results."""
    return hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:32]


def text_transformations(query: str, lang: str) -> list[InlineQueryResultArticle]:
    """Ready-to-send formatted variants of the typed text."""
    escaped = html.escape(query)
    variants = {
        "bold": f"<b>{escaped}</b>",
        "italic": f"<i>{escaped}</i>",
        "code": f"<code>{escaped}</code>",
        "spoiler": f"<tg-spoiler>{escaped}</tg-spoiler>",
        "upper": html.escape(query.upper()),
        "reversed": html.escape(query[::-1]),
    }
    return [
        InlineQueryResultArticle(
            id=_result_id("fmt", kind, query),
            title=t(f"inline.{kind}", lang),
            description=query[:MAX_QUERY_PREVIEW],
            input_message_content=InputTextMessageContent(text),
        )
        for kind, text in variants.items()
    ]


def catalog_results(query: str, lang: str, bot_username: str) -> list[InlineQueryResultArticle]:
    return [
        InlineQueryResultArticle(
            id=_result_id("item", item.id),
            title=f"{item.emoji} {item.name}",
            description=item.describe(lang),
            url=item.url,
            input_message_content=InputTextMessageContent(
                f"{item.emoji} <b>{html.escape(item.name)}</b>\n"
                f"{html.escape(item.describe(lang))}\n{item.url}"
            ),
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            t("inline.open_in_bot", lang), url=item_link(bot_username, item.id)
                        )
                    ]
                ]
            ),
        )
        for item in catalog.search(query, lang, limit=10)
    ]


async def inline_query(update: Update, context: BotContext) -> None:
    query = update.inline_query
    assert query is not None
    lang = context.lang
    text = query.query.strip()

    results: list[InlineQueryResultArticle] = []
    if text:
        results += text_transformations(text, lang)
    results += catalog_results(text, lang, context.bot.username)

    await query.answer(
        results[:50],  # Telegram accepts at most 50 results per answer
        cache_time=10,
        is_personal=True,
        button=InlineQueryResultsButton(t("inline.open_bot", lang), start_parameter="inline"),
    )


def register(app: Application) -> None:
    app.add_handler(InlineQueryHandler(inline_query))
