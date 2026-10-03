"""/settings: per-user language stored in SQLite."""

from __future__ import annotations

from telegram import Update
from telegram.constants import ChatType
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler

from bot.context import LANG_KEY, BotContext
from bot.handlers.common import reply_or_edit
from bot.i18n import i18n
from bot.keyboards import inline, reply
from bot.keyboards.callbacks import pattern, unpack


async def _render(update: Update, context: BotContext) -> None:
    user = update.effective_user
    assert user is not None
    record = await context.services.users.get(user.id)
    chosen = record.language if record else None
    current = inline.LANGUAGE_FLAGS.get(context.lang, context.lang)
    text = context.t("settings.title", language=current)
    if chosen is None:
        text += "\n" + context.t("settings.auto_hint")
    await reply_or_edit(update, text, inline.settings_menu(context.lang, chosen))


async def settings_command(update: Update, context: BotContext) -> None:
    await _render(update, context)


async def settings_callback(update: Update, context: BotContext) -> None:
    query = update.callback_query
    user = update.effective_user
    assert query is not None and user is not None
    match unpack(query.data):
        case ["settings", "open"]:
            await _render(update, context)
        case ["settings", "lang", code]:
            chosen = None if code == "auto" else code
            if chosen is not None and chosen not in i18n.languages:
                await query.answer()
                return
            await context.services.users.set_language(user.id, chosen)
            record = await context.services.users.get(user.id)
            assert context.user_data is not None
            context.user_data[LANG_KEY] = i18n.resolve(
                chosen, record.language_code if record else None, context.settings.default_language
            )
            await _render(update, context)
            # Reply keyboards cannot be edited, so send a new one in the new language.
            if query.message is not None and query.message.chat.type == ChatType.PRIVATE:
                await context.bot.send_message(
                    query.message.chat.id,
                    context.t("settings.saved"),
                    reply_markup=reply.main_menu(context.lang),
                )
        case _:
            await query.answer()


def register(app: Application) -> None:
    app.add_handlers(
        [
            CommandHandler("settings", settings_command),
            MessageHandler(reply.button_filter("btn.settings"), settings_command),
            CallbackQueryHandler(settings_callback, pattern=pattern("settings")),
        ]
    )
