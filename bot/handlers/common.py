"""Helpers shared by handlers."""

from __future__ import annotations

from telegram import InlineKeyboardMarkup, Message, Update
from telegram.error import BadRequest


async def reply_or_edit(
    update: Update, text: str, reply_markup: InlineKeyboardMarkup | None = None
) -> Message | bool | None:
    """Edit the message when called from an inline button, otherwise send a new one.

    This lets the same handler serve both ``/catalog`` and a ``catalog:page:N`` button.
    """
    query = update.callback_query
    if query is not None:
        await query.answer()
        if query.message is not None and getattr(query.message, "text", None) is not None:
            try:
                return await query.edit_message_text(text, reply_markup=reply_markup)
            except BadRequest as exc:  # the user pressed the same button twice
                if "not modified" not in str(exc).lower():
                    raise
                return None
        if query.message is not None:
            return await query.message.reply_text(text, reply_markup=reply_markup)  # type: ignore[union-attr]
        return None
    if update.effective_message is not None:
        return await update.effective_message.reply_text(text, reply_markup=reply_markup)
    return None
