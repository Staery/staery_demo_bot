"""Sending and receiving media: photos, albums, documents, locations, venues, contacts,
dice, polls and quizzes."""

from __future__ import annotations

import html
import io
import json
import logging
import secrets

from telegram import InputFile, InputMediaPhoto, Poll, Update
from telegram.constants import ChatAction, DiceEmoji
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    PollAnswerHandler,
    filters,
)

from bot.context import BotContext
from bot.handlers.common import reply_or_edit
from bot.i18n import t
from bot.keyboards import inline, reply
from bot.keyboards.callbacks import pattern, unpack
from bot.services.formatting import haversine_km, human_size, to_seconds
from bot.services.quiz import random_question

logger = logging.getLogger(__name__)

# A well-known place used for the location / venue demos and distance calculation.
EIFFEL_TOWER = (48.858370, 2.294481)
POLLS_KEY = "polls"  # bot_data: poll_id -> (chat_id, options)
DICE_RESULT_DELAY = 4  # seconds: wait for the dice animation to finish


def random_photo_url() -> str:
    return f"https://picsum.photos/seed/{secrets.token_hex(4)}/800/500"


# --------------------------------------------------------------------------- sending


async def media_menu(update: Update, context: BotContext) -> None:
    await reply_or_edit(update, context.t("media.menu"), inline.media_menu(context.lang))


async def send_photo(update: Update, context: BotContext) -> None:
    chat = update.effective_chat
    assert chat is not None
    await context.bot.send_chat_action(chat.id, ChatAction.UPLOAD_PHOTO)
    await context.bot.send_photo(
        chat.id,
        random_photo_url(),
        caption=context.t("media.photo_caption"),
        reply_markup=inline.another_photo(context.lang),
    )


async def next_photo(update: Update, context: BotContext) -> None:
    """Replace the photo of an existing message (``editMessageMedia``)."""
    query = update.callback_query
    assert query is not None
    await query.answer()
    await query.edit_message_media(
        InputMediaPhoto(random_photo_url(), caption=context.t("media.photo_caption")),
        reply_markup=inline.another_photo(context.lang),
    )


async def send_album(update: Update, context: BotContext) -> None:
    chat = update.effective_chat
    assert chat is not None
    await context.bot.send_chat_action(chat.id, ChatAction.UPLOAD_PHOTO)
    media = [
        InputMediaPhoto(
            random_photo_url(), caption=context.t("media.album_caption") if i == 0 else None
        )
        for i in range(3)
    ]
    await context.bot.send_media_group(chat.id, media)


async def send_document(update: Update, context: BotContext) -> None:
    """Generate a file in memory and upload it: no temporary files on disk."""
    chat, user = update.effective_chat, update.effective_user
    assert chat is not None and user is not None
    await context.bot.send_chat_action(chat.id, ChatAction.UPLOAD_DOCUMENT)
    record = await context.services.users.get(user.id)
    profile = {
        "id": user.id,
        "first_name": user.first_name,
        "username": user.username,
        "language_code": user.language_code,
        "bot_language": context.lang,
        "first_seen": record.created_at.isoformat() if record else None,
        "referrals": await context.services.users.count_referrals(user.id),
    }
    payload = json.dumps(profile, ensure_ascii=False, indent=2).encode()
    await context.bot.send_document(
        chat.id,
        InputFile(io.BytesIO(payload), filename=f"profile_{user.id}.json"),
        caption=context.t("media.document_caption"),
    )


async def send_location(update: Update, context: BotContext) -> None:
    chat = update.effective_chat
    assert chat is not None
    await context.bot.send_location(chat.id, *EIFFEL_TOWER)


async def send_venue(update: Update, context: BotContext) -> None:
    chat = update.effective_chat
    assert chat is not None
    await context.bot.send_venue(
        chat.id,
        *EIFFEL_TOWER,
        title=context.t("media.venue_title"),
        address="Champ de Mars, 5 Av. Anatole France, 75007 Paris",
    )


async def send_contact(update: Update, context: BotContext) -> None:
    chat = update.effective_chat
    assert chat is not None
    # 555-01xx numbers are reserved for fictional use.
    await context.bot.send_contact(
        chat.id, phone_number="+15550100", first_name="Demo", last_name="Contact"
    )


async def send_poll(update: Update, context: BotContext) -> None:
    """A regular, non-anonymous poll: answers arrive as ``PollAnswer`` updates."""
    chat = update.effective_chat
    assert chat is not None
    options = [context.t(f"poll.option{i}") for i in range(1, 5)]
    message = await context.bot.send_poll(
        chat.id, context.t("poll.question"), options, is_anonymous=False
    )
    assert message.poll is not None
    context.bot_data.setdefault(POLLS_KEY, {})[message.poll.id] = (chat.id, options)


async def send_quiz(update: Update, context: BotContext) -> None:
    chat = update.effective_chat
    assert chat is not None
    question = random_question()
    lang = context.lang if context.lang in question.question else "en"
    await context.bot.send_poll(
        chat.id,
        question.question[lang],
        question.options[lang],
        type=Poll.QUIZ,
        correct_option_id=question.correct,  # type: ignore[arg-type]
        explanation=question.explanation[lang],
        is_anonymous=True,
    )


async def poll_answer(update: Update, context: BotContext) -> None:
    answer = update.poll_answer
    assert answer is not None
    polls: dict[str, tuple[int, list[str]]] = context.bot_data.get(POLLS_KEY, {})
    if answer.poll_id not in polls or answer.user is None:
        return
    chat_id, options = polls[answer.poll_id]
    lang = await context.services.language_for(answer.user.id)
    name = html.escape(answer.user.first_name)
    if answer.option_ids:  # an empty list means the vote was retracted
        chosen = html.escape(", ".join(options[i] for i in answer.option_ids))
        text = t("poll.voted", lang, name=name, option=chosen)
    else:
        text = t("poll.retracted", lang, name=name)
    await context.bot.send_message(chat_id, text)


async def dice_menu(update: Update, context: BotContext) -> None:
    await reply_or_edit(update, context.t("dice.choose"), inline.dice_menu())


async def roll_dice(update: Update, context: BotContext, emoji: DiceEmoji = DiceEmoji.DICE) -> None:
    chat = update.effective_chat
    assert chat is not None
    message = await context.bot.send_dice(chat.id, emoji=emoji)
    assert message.dice is not None
    # Announce the result only after the animation has finished playing.
    context.job_queue.run_once(  # type: ignore[union-attr]
        _announce_dice,
        DICE_RESULT_DELAY,
        data=(message.message_id, message.dice.value, context.lang),
        chat_id=chat.id,
    )


async def _announce_dice(context: BotContext) -> None:
    assert context.job is not None and context.job.chat_id is not None
    message_id, value, lang = context.job.data  # type: ignore[misc]
    await context.bot.send_message(
        context.job.chat_id, t("dice.result", lang, value=value), reply_to_message_id=message_id
    )


async def dice_command(update: Update, context: BotContext) -> None:
    """``/dice`` rolls a die, ``/dice 🎯`` throws a dart, etc."""
    if context.args and context.args[0] in {e.value for e in DiceEmoji}:
        await roll_dice(update, context, DiceEmoji(context.args[0]))
    else:
        await dice_menu(update, context)


async def media_callback(update: Update, context: BotContext) -> None:
    query = update.callback_query
    assert query is not None
    action = unpack(query.data)[1:]
    senders = {
        "photo": send_photo,
        "album": send_album,
        "document": send_document,
        "location": send_location,
        "venue": send_venue,
        "contact": send_contact,
        "poll": send_poll,
        "quiz": send_quiz,
    }
    match action:
        case ["menu"]:
            await media_menu(update, context)
        case ["next"]:
            await next_photo(update, context)
        case [kind] if kind in senders:
            await query.answer()
            await senders[kind](update, context)
        case _:
            await query.answer()


async def dice_callback(update: Update, context: BotContext) -> None:
    query = update.callback_query
    assert query is not None
    match unpack(query.data):
        case ["dice", "menu"]:
            await dice_menu(update, context)
        case ["dice", name] if name in DiceEmoji.__members__:
            await query.answer()
            await roll_dice(update, context, DiceEmoji[name])
        case _:
            await query.answer()


# --------------------------------------------------------------------------- receiving


async def on_photo(update: Update, context: BotContext) -> None:
    message = update.effective_message
    assert message is not None and message.photo
    largest = message.photo[-1]  # sizes are sorted from smallest to largest
    # Re-sending by file_id costs nothing: Telegram already has the file.
    await message.reply_photo(
        largest.file_id,
        caption=context.t(
            "incoming.photo",
            width=largest.width,
            height=largest.height,
            size=human_size(largest.file_size),
            count=len(message.photo),
        ),
    )


async def on_document(update: Update, context: BotContext) -> None:
    message = update.effective_message
    assert message is not None and message.document is not None
    document = message.document
    await message.reply_text(
        context.t(
            "incoming.document",
            name=html.escape(document.file_name or "?"),
            mime=html.escape(document.mime_type or "?"),
            size=human_size(document.file_size),
        )
    )


async def on_voice(update: Update, context: BotContext) -> None:
    message = update.effective_message
    assert message is not None and message.voice is not None
    voice = message.voice
    await message.reply_text(
        context.t(
            "incoming.voice", duration=to_seconds(voice.duration), size=human_size(voice.file_size)
        )
    )


async def on_location(update: Update, context: BotContext) -> None:
    message = update.effective_message
    assert message is not None and message.location is not None
    location = message.location
    distance = haversine_km(location.latitude, location.longitude, *EIFFEL_TOWER)
    await message.reply_text(
        context.t(
            "incoming.location",
            lat=f"{location.latitude:.5f}",
            lon=f"{location.longitude:.5f}",
            distance=f"{distance:,.1f}",
        )
    )


async def on_contact(update: Update, context: BotContext) -> None:
    message = update.effective_message
    user = update.effective_user
    assert message is not None and message.contact is not None and user is not None
    contact = message.contact
    key = "incoming.contact_own" if contact.user_id == user.id else "incoming.contact_other"
    # The phone number is intentionally not stored anywhere.
    await message.reply_text(context.t(key, name=html.escape(contact.first_name)))


async def on_sticker(update: Update, context: BotContext) -> None:
    message = update.effective_message
    assert message is not None and message.sticker is not None
    sticker = message.sticker
    await message.reply_text(
        context.t(
            "incoming.sticker",
            emoji=sticker.emoji or "",
            set_name=html.escape(sticker.set_name or "—"),
        )
    )


def register(app: Application) -> None:
    private = filters.ChatType.PRIVATE
    app.add_handlers(
        [
            CommandHandler("media", media_menu),
            MessageHandler(reply.button_filter("btn.media"), media_menu),
            CommandHandler("photo", send_photo),
            CommandHandler("dice", dice_command),
            CommandHandler("poll", send_poll),
            CommandHandler("quiz", send_quiz),
            CallbackQueryHandler(media_callback, pattern=pattern("media")),
            CallbackQueryHandler(dice_callback, pattern=pattern("dice")),
            PollAnswerHandler(poll_answer),
            MessageHandler(private & filters.PHOTO, on_photo),
            MessageHandler(private & filters.Document.ALL, on_document),
            MessageHandler(private & filters.VOICE, on_voice),
            MessageHandler(private & filters.LOCATION, on_location),
            MessageHandler(private & filters.CONTACT, on_contact),
            MessageHandler(private & filters.Sticker.ALL, on_sticker),
        ]
    )
