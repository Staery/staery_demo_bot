"""Anti-flood: drop updates from users who send too many messages or button presses."""

from __future__ import annotations

import logging
import math

from telegram import Update
from telegram.ext import ApplicationHandlerStop

from bot.context import BotContext

logger = logging.getLogger(__name__)


async def anti_flood(update: Update, context: BotContext) -> None:
    user = update.effective_user
    # Inline queries arrive on every keystroke, so they are not throttled here.
    if user is None or not (update.message or update.callback_query):
        return
    if context.settings.is_admin(user.id):
        return

    decision = context.services.rate_limiter.hit(user.id)
    if decision.allowed:
        return

    logger.info("Throttled user %s (retry in %.1fs)", user.id, decision.retry_after)
    query = update.callback_query
    if decision.should_warn:
        text = context.t("flood.warning", seconds=math.ceil(decision.retry_after))
        if query:
            await query.answer(text, show_alert=True)
        elif update.message:
            await update.message.reply_text(text)
    elif query:
        await query.answer()  # stop the loading spinner on the button
    raise ApplicationHandlerStop
