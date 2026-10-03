"""Message editing, deletion and chat actions.

These handlers wait between steps, so they are registered with ``block=False``:
the application keeps processing other updates while they run.
"""

from __future__ import annotations

import asyncio

from telegram import Update
from telegram.constants import ChatAction
from telegram.error import TelegramError
from telegram.ext import Application, CommandHandler

from bot.context import BotContext

COUNTDOWN = ("3️⃣", "2️⃣", "1️⃣")
DEFAULT_SELF_DESTRUCT = 10
MAX_SELF_DESTRUCT = 300


async def countdown(update: Update, context: BotContext) -> None:
    """Edit the same message several times (``editMessageText``)."""
    message = update.effective_message
    assert message is not None
    sent = await message.reply_text(COUNTDOWN[0])
    for frame in COUNTDOWN[1:]:
        await asyncio.sleep(1)
        await sent.edit_text(frame)
    await asyncio.sleep(1)
    await sent.edit_text(context.t("effects.liftoff"))


async def typing(update: Update, context: BotContext) -> None:
    """Show "typing…" in the chat header while "thinking" (``sendChatAction``)."""
    chat, message = update.effective_chat, update.effective_message
    assert chat is not None and message is not None
    # A chat action lasts ~5 seconds or until the bot sends a message.
    await context.bot.send_chat_action(chat.id, ChatAction.TYPING)
    await asyncio.sleep(3)
    await message.reply_text(context.t("effects.typed"))


async def self_destruct(update: Update, context: BotContext) -> None:
    """``/selfdestruct [seconds]``: delete a message later with a JobQueue job."""
    chat, message = update.effective_chat, update.effective_message
    assert chat is not None and message is not None
    seconds = DEFAULT_SELF_DESTRUCT
    if context.args and context.args[0].isdigit():
        seconds = max(1, min(int(context.args[0]), MAX_SELF_DESTRUCT))
    sent = await message.reply_text(context.t("effects.self_destruct", seconds=seconds))
    assert context.job_queue is not None
    context.job_queue.run_once(
        _delete_messages,
        seconds,
        data=[sent.message_id, message.message_id],
        chat_id=chat.id,
        name=f"selfdestruct:{chat.id}:{sent.message_id}",
    )


async def _delete_messages(context: BotContext) -> None:
    job = context.job
    assert job is not None and job.chat_id is not None
    try:
        # In groups the bot needs the "delete messages" right to remove the user's command.
        await context.bot.delete_messages(job.chat_id, job.data)  # type: ignore[arg-type]
    except TelegramError:
        await context.bot.delete_message(job.chat_id, job.data[0])  # type: ignore[index]


def register(app: Application) -> None:
    app.add_handlers(
        [
            CommandHandler("countdown", countdown, block=False),
            CommandHandler("typing", typing, block=False),
            CommandHandler("selfdestruct", self_destruct),
        ]
    )
