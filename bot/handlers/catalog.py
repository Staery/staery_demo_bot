"""Paginated catalogue with inline keyboards and in-place message editing."""

from __future__ import annotations

import html

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler

from bot.context import BotContext
from bot.handlers.common import reply_or_edit
from bot.keyboards import inline, reply
from bot.keyboards.callbacks import pattern, unpack
from bot.services import catalog
from bot.services.deep_links import item_link
from bot.services.pagination import paginate


def _item_text(context: BotContext, item: catalog.CatalogItem) -> str:
    return context.t(
        "catalog.item",
        emoji=item.emoji,
        name=html.escape(item.name),
        description=html.escape(item.describe(context.lang)),
        link=item_link(context.bot.username, item.id),
    )


async def show_page(update: Update, context: BotContext, page_number: int = 0) -> None:
    page = paginate(catalog.ITEMS, page_number, catalog.PER_PAGE)
    text = context.t(
        "catalog.title", page=page.number + 1, pages=page.total_pages, total=page.total_items
    )
    await reply_or_edit(update, text, inline.catalog_page(page, context.lang))


async def send_item_card(
    update: Update, context: BotContext, item_id: int, back_page: int = 0
) -> None:
    item = catalog.get_item(item_id)
    if item is None:
        await reply_or_edit(update, context.t("catalog.not_found"))
        return
    await reply_or_edit(
        update, _item_text(context, item), inline.catalog_item(item, back_page, context.lang)
    )


async def catalog_command(update: Update, context: BotContext) -> None:
    await show_page(update, context)


async def catalog_callback(update: Update, context: BotContext) -> None:
    """Handles ``catalog:page:<n>``, ``catalog:item:<id>:<page>`` and ``catalog:noop``."""
    query = update.callback_query
    assert query is not None
    parts = unpack(query.data)
    match parts:
        case ["catalog", "page", page]:
            await show_page(update, context, int(page))
        case ["catalog", "item", item_id, page]:
            await send_item_card(update, context, int(item_id), int(page))
        case _:
            await query.answer()


def register(app: Application) -> None:
    app.add_handlers(
        [
            CommandHandler("catalog", catalog_command),
            MessageHandler(reply.button_filter("btn.catalog"), catalog_command),
            CallbackQueryHandler(catalog_callback, pattern=pattern("catalog")),
        ]
    )
