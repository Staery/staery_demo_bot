"""/start (with deep links), /menu, /help and /invite."""

from __future__ import annotations

import html
from urllib.parse import quote

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatType
from telegram.ext import Application, CommandHandler, MessageHandler

from bot.commands import help_text
from bot.context import BotContext
from bot.handlers.catalog import send_item_card
from bot.keyboards import inline, reply
from bot.middlewares.user_tracking import NEW_USER_KEY
from bot.services.deep_links import PayloadKind, parse_start_payload, referral_link


def _share_url(context: BotContext, user_id: int) -> str:
    link = referral_link(context.bot.username, user_id)
    return f"https://t.me/share/url?url={quote(link)}&text={quote(context.t('invite.share_text'))}"


async def start(update: Update, context: BotContext) -> None:
    """``/start [payload]``. Payloads come from links like ``t.me/<bot>?start=ref_42``."""
    user = update.effective_user
    message = update.effective_message
    if user is None or message is None:
        return

    payload = parse_start_payload(context.args)
    users = context.services.users
    is_new = bool(context.user_data and context.user_data.get(NEW_USER_KEY))

    # Referral links only count for brand-new users.
    if (
        payload.kind is PayloadKind.REFERRAL
        and payload.value is not None
        and is_new
        and await users.set_referrer(user.id, payload.value)
    ):
        await message.reply_text(context.t("start.referral_ok"))

    greeting = "start.welcome" if is_new else "start.welcome_back"
    await message.reply_text(
        context.t(greeting, name=html.escape(user.first_name)),
        reply_markup=reply.main_menu(context.lang)
        if message.chat.type == ChatType.PRIVATE
        else None,
    )

    if payload.kind is PayloadKind.ITEM and payload.value is not None:
        await send_item_card(update, context, payload.value)
        return
    await menu(update, context)


async def menu(update: Update, context: BotContext) -> None:
    if update.effective_message is None or update.effective_user is None:
        return
    await update.effective_message.reply_text(
        context.t("menu.title"),
        reply_markup=inline.main_menu(context.lang, _share_url(context, update.effective_user.id)),
    )


async def help_command(update: Update, context: BotContext) -> None:
    if update.effective_message is None:
        return
    user_id = update.effective_user.id if update.effective_user else None
    await update.effective_message.reply_text(
        help_text(context.lang, admin=context.settings.is_admin(user_id))
    )


async def invite(update: Update, context: BotContext) -> None:
    user = update.effective_user
    if user is None or update.effective_message is None:
        return
    count = await context.services.users.count_referrals(user.id)
    link = referral_link(context.bot.username, user.id)
    await update.effective_message.reply_text(
        context.t("invite.text", link=link, count=count),
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton(context.t("btn.invite"), url=_share_url(context, user.id))]]
        ),
    )


def register(app: Application) -> None:
    app.add_handlers(
        [
            CommandHandler("start", start),
            CommandHandler("menu", menu),
            CommandHandler("help", help_command),
            CommandHandler("invite", invite),
            MessageHandler(reply.button_filter("btn.help"), help_command),
        ]
    )
