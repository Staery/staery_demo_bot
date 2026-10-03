"""Catch-all handlers. Registered last, so they only see what nobody else handled."""

from __future__ import annotations

import html

from telegram import Update
from telegram.ext import Application, MessageHandler, filters

from bot.context import BotContext


async def unknown_command(update: Update, context: BotContext) -> None:
    assert update.effective_message is not None
    await update.effective_message.reply_text(context.t("fallback.unknown_command"))


async def echo(update: Update, context: BotContext) -> None:
    message = update.effective_message
    assert message is not None and message.text is not None
    await message.reply_text(context.t("fallback.echo", text=html.escape(message.text)))


def register(app: Application) -> None:
    private = filters.ChatType.PRIVATE
    app.add_handlers(
        [
            MessageHandler(private & filters.COMMAND, unknown_command),
            MessageHandler(private & filters.TEXT & ~filters.COMMAND, echo),
        ]
    )
