"""Group and membership events: welcome messages and blocked/unblocked tracking."""

from __future__ import annotations

import html
import logging

from telegram import ChatMember, ChatMemberUpdated, Update
from telegram.constants import ChatType
from telegram.ext import Application, ChatMemberHandler, MessageHandler, filters

from bot.context import BotContext

logger = logging.getLogger(__name__)


async def new_members(update: Update, context: BotContext) -> None:
    message = update.effective_message
    assert message is not None
    for member in message.new_chat_members:
        if member.id == context.bot.id:
            await message.reply_text(context.t("groups.bot_added"))
        elif not member.is_bot:
            await message.reply_text(
                context.t("groups.welcome", name=html.escape(member.full_name))
            )


def _is_member(status: str) -> bool:
    return status in {ChatMember.MEMBER, ChatMember.ADMINISTRATOR, ChatMember.OWNER}


async def my_chat_member(update: Update, context: BotContext) -> None:
    """The bot's own membership changed: blocked/unblocked in private, added/removed in groups."""
    change: ChatMemberUpdated | None = update.my_chat_member
    assert change is not None
    was, now = _is_member(change.old_chat_member.status), _is_member(change.new_chat_member.status)
    if change.chat.type == ChatType.PRIVATE:
        if was and not now:
            logger.info("User %s blocked the bot", change.from_user.id)
            await context.services.users.set_blocked(change.from_user.id, True)
        elif now and not was:
            logger.info("User %s unblocked the bot", change.from_user.id)
            await context.services.users.set_blocked(change.from_user.id, False)
    elif was != now:
        action = "added to" if now else "removed from"
        logger.info(
            "Bot was %s %s (%s) by %s",
            action,
            change.chat.title,
            change.chat.id,
            change.from_user.id,
        )


def register(app: Application) -> None:
    app.add_handlers(
        [
            MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_members),
            ChatMemberHandler(my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER),
        ]
    )
