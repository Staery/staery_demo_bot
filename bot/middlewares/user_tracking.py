"""Persist every user we see and resolve their interface language."""

from __future__ import annotations

from telegram import Update

from bot.context import LANG_KEY, BotContext
from bot.i18n import i18n

NEW_USER_KEY = "is_new_user"


async def track_user(update: Update, context: BotContext) -> None:
    user = update.effective_user
    # ``my_chat_member`` updates are handled separately: they report that the user
    # blocked or unblocked the bot, so they must not refresh the "active" flag.
    if user is None or user.is_bot or update.my_chat_member or context.user_data is None:
        return

    record, created = await context.services.users.upsert(
        user_id=user.id,
        first_name=user.first_name,
        username=user.username,
        language_code=user.language_code,
    )
    context.user_data[LANG_KEY] = i18n.resolve(
        record.language, record.language_code, context.settings.default_language
    )
    context.user_data[NEW_USER_KEY] = created
