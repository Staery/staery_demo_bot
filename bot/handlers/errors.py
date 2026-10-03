"""Global error handler: log the traceback, apologise to the user, notify admins."""

from __future__ import annotations

import html
import json
import logging
import traceback

from telegram import Update
from telegram.error import TelegramError

from bot.context import BotContext

logger = logging.getLogger(__name__)

MAX_REPORT_LENGTH = 3500


def build_report(update: object, error: BaseException | None) -> str:
    """HTML error report for admins, trimmed to fit into one Telegram message."""
    tb = "".join(traceback.format_exception(error)) if error else "no exception"
    update_repr = (
        json.dumps(update.to_dict(), indent=1, ensure_ascii=False)
        if isinstance(update, Update)
        else str(update)
    )
    half = MAX_REPORT_LENGTH // 2
    return (
        "⚠️ <b>Unhandled exception</b>\n"
        f"<pre>{html.escape(update_repr[:half])}</pre>\n"
        f"<pre>{html.escape(tb[-half:])}</pre>"
    )


async def error_handler(update: object, context: BotContext) -> None:
    logger.error("Exception while handling an update", exc_info=context.error)

    if isinstance(update, Update) and update.effective_message is not None:
        try:
            await update.effective_message.reply_text(context.t("errors.generic"))
        except TelegramError:
            logger.debug("Could not send the error message to the user", exc_info=True)

    report = build_report(update, context.error)
    for admin_id in context.settings.admin_ids:
        try:
            await context.bot.send_message(admin_id, report)
        except TelegramError:
            logger.debug("Could not send the error report to admin %s", admin_id, exc_info=True)
