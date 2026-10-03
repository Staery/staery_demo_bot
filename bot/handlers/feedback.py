"""Feedback form: a multi-step ConversationHandler (finite-state machine).

    NAME -> EMAIL (optional, /skip) -> RATING (inline stars) -> MESSAGE -> CONFIRM

Every step validates its input and re-asks on error. ``/cancel`` (or the Cancel button)
leaves the conversation at any step; it also times out after 10 minutes of inactivity.
"""

from __future__ import annotations

import html
import logging
import warnings
from enum import IntEnum, auto

from telegram import ReplyKeyboardRemove, Update
from telegram.constants import ChatType
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)
from telegram.warnings import PTBUserWarning

from bot.context import BotContext
from bot.keyboards import inline, reply
from bot.keyboards.callbacks import pack, unpack
from bot.services.validators import (
    ValidationError,
    validate_email,
    validate_message,
    validate_name,
    validate_rating,
)
from bot.storage import FeedbackRecord

logger = logging.getLogger(__name__)

FORM_KEY = "feedback_form"
TIMEOUT_SECONDS = 600


class State(IntEnum):
    NAME = auto()
    EMAIL = auto()
    RATING = auto()
    MESSAGE = auto()
    CONFIRM = auto()


def _form(context: BotContext) -> dict[str, object]:
    assert context.user_data is not None
    return context.user_data.setdefault(FORM_KEY, {})


async def _say(update: Update, text: str, **kwargs: object) -> None:
    message = update.effective_message
    if message is not None:
        await message.reply_text(text, **kwargs)  # type: ignore[arg-type]


async def _error(update: Update, context: BotContext, error: ValidationError) -> None:
    await _say(update, "⚠️ " + context.t(error.key, **error.params))


async def start(update: Update, context: BotContext) -> State | int:
    chat = update.effective_chat
    if chat is not None and chat.type != ChatType.PRIVATE:
        await _say(update, context.t("feedback.private_only"))
        return ConversationHandler.END
    if update.callback_query:
        await update.callback_query.answer()
    _form(context).clear()
    user = update.effective_user
    suggestions = [[user.full_name]] if user and user.full_name else []
    await _say(
        update,
        context.t("feedback.ask_name"),
        reply_markup=reply.cancel_keyboard(context.lang, *suggestions),
    )
    return State.NAME


async def got_name(update: Update, context: BotContext) -> State:
    assert update.message is not None and update.message.text is not None
    try:
        _form(context)["name"] = validate_name(update.message.text)
    except ValidationError as error:
        await _error(update, context, error)
        return State.NAME
    await _say(
        update, context.t("feedback.ask_email"), reply_markup=reply.cancel_keyboard(context.lang)
    )
    return State.EMAIL


async def got_email(update: Update, context: BotContext) -> State:
    assert update.message is not None and update.message.text is not None
    try:
        _form(context)["email"] = validate_email(update.message.text)
    except ValidationError as error:
        await _error(update, context, error)
        return State.EMAIL
    return await _ask_rating(update, context)


async def skip_email(update: Update, context: BotContext) -> State:
    _form(context)["email"] = ""
    return await _ask_rating(update, context)


async def _ask_rating(update: Update, context: BotContext) -> State:
    await _say(update, context.t("feedback.ask_rating"), reply_markup=inline.rating(context.lang))
    return State.RATING


async def got_rating(update: Update, context: BotContext) -> State:
    query = update.callback_query
    try:
        if query is not None:
            await query.answer()
            value = validate_rating(unpack(query.data)[-1])
            await query.edit_message_text(context.t("feedback.rated", stars="⭐" * value))
        else:
            assert update.message is not None and update.message.text is not None
            value = validate_rating(update.message.text)
    except ValidationError as error:
        await _error(update, context, error)
        return State.RATING
    _form(context)["rating"] = value
    await _say(
        update, context.t("feedback.ask_message"), reply_markup=reply.cancel_keyboard(context.lang)
    )
    return State.MESSAGE


async def got_message(update: Update, context: BotContext) -> State:
    assert update.message is not None and update.message.text is not None
    try:
        _form(context)["message"] = validate_message(update.message.text)
    except ValidationError as error:
        await _error(update, context, error)
        return State.MESSAGE

    form = _form(context)
    await _say(update, context.t("feedback.almost_done"), reply_markup=ReplyKeyboardRemove())
    await _say(
        update,
        context.t(
            "feedback.summary",
            name=html.escape(str(form["name"])),
            email=html.escape(str(form["email"])) or "—",
            stars="⭐" * int(form["rating"]),  # type: ignore[call-overload]
            message=html.escape(str(form["message"])),
        ),
        reply_markup=inline.feedback_confirm(context.lang),
    )
    return State.CONFIRM


async def confirm(update: Update, context: BotContext) -> State | int:
    query = update.callback_query
    user = update.effective_user
    assert query is not None and user is not None
    action = unpack(query.data)[-1]

    if action == "restart":
        await query.edit_message_reply_markup(None)
        return await start(update, context)  # start() answers the callback query
    if action != "send":
        return await cancel(update, context)

    await query.answer()
    form = _form(context)
    record = FeedbackRecord(
        user_id=user.id,
        name=str(form["name"]),
        email=str(form["email"]),
        rating=int(form["rating"]),  # type: ignore[call-overload]
        message=str(form["message"]),
    )
    feedback_id = await context.services.feedback.add(record)
    form.clear()
    await query.edit_message_text(context.t("feedback.thanks", id=feedback_id))
    await _say(update, context.t("menu.back"), reply_markup=reply.main_menu(context.lang))
    await _notify_admins(context, record, feedback_id)
    return ConversationHandler.END


async def _notify_admins(context: BotContext, record: FeedbackRecord, feedback_id: int) -> None:
    text = (
        f"📝 <b>Feedback #{feedback_id}</b> from <code>{record.user_id}</code>\n"
        f"{html.escape(record.name)} {html.escape(record.email)}\n"
        f"{'⭐' * record.rating}\n\n{html.escape(record.message)}"
    )
    for admin_id in context.settings.admin_ids:
        try:
            await context.bot.send_message(admin_id, text)
        except TelegramError as exc:
            logger.warning("Could not notify admin %s: %s", admin_id, exc)


async def cancel(update: Update, context: BotContext) -> int:
    _form(context).clear()
    if update.callback_query is not None:
        await update.callback_query.answer()
        await update.callback_query.edit_message_reply_markup(None)
    await _say(update, context.t("feedback.cancelled"), reply_markup=reply.main_menu(context.lang))
    return ConversationHandler.END


async def timeout(update: Update, context: BotContext) -> None:
    _form(context).clear()
    await _say(update, context.t("feedback.timeout"), reply_markup=reply.main_menu(context.lang))


def build_conversation() -> ConversationHandler:
    text = filters.TEXT & ~filters.COMMAND
    cancel_button = reply.button_filter("btn.cancel")
    answer = text & ~cancel_button

    with warnings.catch_warnings():
        # Mixing message and callback handlers with per_message=False is intentional here:
        # the conversation is tracked per user and chat, not per message.
        warnings.filterwarnings("ignore", category=PTBUserWarning, message=".*per_message.*")
        return ConversationHandler(
            name="feedback",
            entry_points=[
                CommandHandler("feedback", start),
                # Deep link: https://t.me/<bot>?start=feedback
                CommandHandler("start", start, filters=filters.Regex(r"^/start feedback$")),
                MessageHandler(reply.button_filter("btn.feedback"), start),
                CallbackQueryHandler(start, pattern=f"^{pack('feedback', 'start')}$"),
            ],
            states={
                State.NAME: [MessageHandler(answer, got_name)],
                State.EMAIL: [
                    CommandHandler("skip", skip_email),
                    MessageHandler(answer, got_email),
                ],
                State.RATING: [
                    CallbackQueryHandler(got_rating, pattern=r"^feedback:rate:\d$"),
                    MessageHandler(answer, got_rating),
                ],
                State.MESSAGE: [MessageHandler(answer, got_message)],
                State.CONFIRM: [
                    CallbackQueryHandler(confirm, pattern=r"^feedback:(send|restart|cancel)$")
                ],
                ConversationHandler.TIMEOUT: [
                    MessageHandler(filters.ALL, timeout),
                    CallbackQueryHandler(timeout),
                ],
            },
            fallbacks=[
                CommandHandler("cancel", cancel),
                MessageHandler(cancel_button, cancel),
                CallbackQueryHandler(cancel, pattern=r"^feedback:cancel$"),
            ],
            allow_reentry=True,
            conversation_timeout=TIMEOUT_SECONDS,
        )


async def cancel_outside(update: Update, context: BotContext) -> None:
    """``/cancel`` when no conversation is active."""
    await _say(update, context.t("cancel.nothing"), reply_markup=reply.main_menu(context.lang))


def register(app: Application) -> None:
    app.add_handler(build_conversation())
    app.add_handlers(
        [
            CommandHandler("cancel", cancel_outside),
            MessageHandler(reply.button_filter("btn.cancel"), cancel_outside),
        ]
    )
