"""Admin-only commands. Admin IDs come from the ``ADMIN_IDS`` environment variable.

For everybody else these commands simply do not exist (they fall through to the
"unknown command" handler).
"""

from __future__ import annotations

import html
import logging
import time
from datetime import timedelta

from telegram import Update
from telegram.error import Forbidden, TelegramError
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, filters

from bot import __version__
from bot.context import BotContext
from bot.keyboards import inline
from bot.keyboards.callbacks import pattern, unpack
from bot.services.durations import format_duration

logger = logging.getLogger(__name__)

STARTED_AT_KEY = "started_at"
BROADCAST_KEY = "pending_broadcast"
PROGRESS_EVERY = 25


async def stats(update: Update, context: BotContext) -> None:
    message = update.effective_message
    assert message is not None
    services = context.services
    users = await services.users.stats()
    feedback_count, avg_rating = await services.feedback.count_and_average()
    pending = len(await services.reminders.pending())
    stars = await services.payments.total("XTR")
    uptime = time.monotonic() - context.bot_data.get(STARTED_AT_KEY, time.monotonic())
    languages = ", ".join(f"{lang}: {n}" for lang, n in users.by_language.items()) or "—"

    await message.reply_text(
        context.t(
            "admin.stats",
            total=users.total,
            active=users.active_24h,
            blocked=users.blocked,
            languages=html.escape(languages),
            feedback=feedback_count,
            rating=avg_rating if avg_rating is not None else "—",
            reminders=pending,
            stars=stars,
            uptime=format_duration(timedelta(seconds=int(uptime)), context.lang),
            version=__version__,
        )
    )


async def broadcast(update: Update, context: BotContext) -> None:
    """``/broadcast <text>`` or reply ``/broadcast`` to any message to copy it to all users."""
    message = update.effective_message
    assert message is not None and context.user_data is not None
    if message.reply_to_message is not None:
        pending = {"chat_id": message.chat_id, "message_id": message.reply_to_message.message_id}
        preview = context.t("admin.broadcast_preview_copy")
    elif context.args:
        # Keep the admin's formatting: text_html re-creates bold/italic/links as HTML.
        text = message.text_html.split(maxsplit=1)[1] if message.text_html else ""
        pending = {"text": text}
        preview = text
    else:
        await message.reply_text(context.t("admin.broadcast_usage"))
        return

    context.user_data[BROADCAST_KEY] = pending
    recipients = len(await context.services.users.active_ids())
    await message.reply_text(
        context.t("admin.broadcast_confirm", count=recipients, preview=preview),
        reply_markup=inline.broadcast_confirm(context.lang),
    )


async def broadcast_callback(update: Update, context: BotContext) -> None:
    query = update.callback_query
    assert query is not None and context.user_data is not None
    if not context.settings.is_admin(query.from_user.id):
        await query.answer()
        return
    await query.answer()
    pending = context.user_data.pop(BROADCAST_KEY, None)
    if unpack(query.data)[-1] != "send" or pending is None:
        await query.edit_message_text(context.t("admin.broadcast_cancelled"))
        return

    users = context.services.users
    recipients = await users.active_ids()
    delivered = failed = blocked = 0
    await query.edit_message_text(
        context.t("admin.broadcast_progress", done=0, total=len(recipients))
    )

    for index, user_id in enumerate(recipients, start=1):
        try:
            if "text" in pending:
                await context.bot.send_message(user_id, pending["text"])
            else:
                await context.bot.copy_message(user_id, pending["chat_id"], pending["message_id"])
            delivered += 1
        except Forbidden:
            blocked += 1
            await users.set_blocked(user_id, True)
        except TelegramError as exc:
            failed += 1
            logger.warning("Broadcast to %s failed: %s", user_id, exc)
        if index % PROGRESS_EVERY == 0:
            await query.edit_message_text(
                context.t("admin.broadcast_progress", done=index, total=len(recipients))
            )

    await query.edit_message_text(
        context.t("admin.broadcast_done", delivered=delivered, blocked=blocked, failed=failed)
    )


def register(app: Application, admin_ids: frozenset[int]) -> None:
    # filters.User with an empty set lets nobody through, which is exactly what we want.
    is_admin = filters.User(user_id=admin_ids)
    app.add_handlers(
        [
            CommandHandler("stats", stats, filters=is_admin),
            CommandHandler("broadcast", broadcast, filters=is_admin),
            # block=False: sending to many users must not stall other updates.
            CallbackQueryHandler(broadcast_callback, pattern=pattern("broadcast"), block=False),
        ]
    )
