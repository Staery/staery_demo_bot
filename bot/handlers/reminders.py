"""``/remind 10m text``: reminders persisted in SQLite and scheduled with the JobQueue.

Pending reminders are re-scheduled on startup, so they survive restarts.
"""

from __future__ import annotations

import html
import logging
from datetime import timedelta

from telegram import Update
from telegram.error import Forbidden
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, JobQueue

from bot.context import BotContext, Services
from bot.handlers.common import reply_or_edit
from bot.i18n import t
from bot.keyboards import inline
from bot.keyboards.callbacks import pattern, unpack
from bot.services.durations import DurationError, format_duration, parse_reminder_args
from bot.storage import ReminderRecord
from bot.storage.repositories import utcnow

logger = logging.getLogger(__name__)

MAX_PENDING_PER_USER = 10
SNOOZE = timedelta(minutes=10)


def job_name(reminder_id: int) -> str:
    return f"reminder:{reminder_id}"


def schedule(job_queue: JobQueue, reminder: ReminderRecord) -> None:
    # A reminder that became due while the bot was offline fires right away.
    when = max(reminder.due_at, utcnow() + timedelta(seconds=1))
    job_queue.run_once(
        fire_reminder,
        when,
        data=reminder.id,
        name=job_name(reminder.id),
        chat_id=reminder.chat_id,
        user_id=reminder.user_id,
    )


async def fire_reminder(context: BotContext) -> None:
    assert context.job is not None
    services = context.services
    reminder = await services.reminders.get(int(context.job.data))  # type: ignore[arg-type]
    if reminder is None or reminder.sent:
        return
    lang = await services.language_for(reminder.user_id)
    try:
        await context.bot.send_message(
            reminder.chat_id,
            t("reminders.fired", lang, text=html.escape(reminder.text)),
            reply_markup=inline.reminder_snooze(reminder.id, lang),
        )
    except Forbidden:
        logger.info("User %s blocked the bot; dropping reminder %s", reminder.user_id, reminder.id)
        await services.users.set_blocked(reminder.user_id, True)
    await services.reminders.mark_sent(reminder.id)


async def _create(
    context: BotContext, user_id: int, chat_id: int, text: str, delay: timedelta
) -> ReminderRecord:
    reminder = await context.services.reminders.add(user_id, chat_id, text, utcnow() + delay)
    assert context.job_queue is not None
    schedule(context.job_queue, reminder)
    return reminder


async def remind(update: Update, context: BotContext) -> None:
    message, user, chat = update.effective_message, update.effective_user, update.effective_chat
    if message is None or user is None or chat is None:
        return
    try:
        delay, text = parse_reminder_args(context.args or [])
    except DurationError as error:
        await message.reply_text(context.t(f"reminders.err_{error.code}"))
        return

    if len(await context.services.reminders.pending(user.id)) >= MAX_PENDING_PER_USER:
        await message.reply_text(context.t("reminders.err_too_many", limit=MAX_PENDING_PER_USER))
        return

    reminder = await _create(context, user.id, chat.id, text, delay)
    await message.reply_text(
        context.t(
            "reminders.created",
            id=reminder.id,
            delay=format_duration(delay, context.lang),
            due=reminder.due_at.strftime("%Y-%m-%d %H:%M UTC"),
        )
    )


async def list_reminders(update: Update, context: BotContext) -> None:
    user = update.effective_user
    assert user is not None
    reminders = await context.services.reminders.pending(user.id)
    if not reminders:
        await reply_or_edit(update, context.t("reminders.empty"))
        return
    now = utcnow()
    lines = [context.t("reminders.list_title")]
    lines += [
        f"#{r.id} · ⏳ {format_duration(r.due_at - now, context.lang)} · {html.escape(r.text)}"
        for r in reminders
    ]
    await reply_or_edit(update, "\n".join(lines), inline.reminders_list(reminders))


async def reminder_callback(update: Update, context: BotContext) -> None:
    query, user = update.callback_query, update.effective_user
    assert query is not None and user is not None
    match unpack(query.data):
        case ["reminder", "del", reminder_id]:
            deleted = await context.services.reminders.delete(int(reminder_id), user.id)
            if deleted and context.job_queue is not None:
                for job in context.job_queue.get_jobs_by_name(job_name(int(reminder_id))):
                    job.schedule_removal()
            await list_reminders(update, context)
        case ["reminder", "snooze", reminder_id]:
            original = await context.services.reminders.get(int(reminder_id))
            if original is None or original.user_id != user.id:
                await query.answer()
                return
            await _create(context, user.id, original.chat_id, original.text, SNOOZE)
            await query.answer(
                context.t("reminders.snoozed", delay=format_duration(SNOOZE, context.lang))
            )
            await query.edit_message_reply_markup(None)
        case _:
            await query.answer()


async def restore_reminders(job_queue: JobQueue, services: Services) -> int:
    pending = await services.reminders.pending()
    for reminder in pending:
        schedule(job_queue, reminder)
    if pending:
        logger.info("Restored %d pending reminder(s)", len(pending))
    return len(pending)


def register(app: Application) -> None:
    app.add_handlers(
        [
            CommandHandler("remind", remind),
            CommandHandler("reminders", list_reminders),
            CallbackQueryHandler(reminder_callback, pattern=pattern("reminder")),
        ]
    )
