"""Telegram Stars payments (currency ``XTR``): invoice -> pre-checkout -> successful payment.

Stars need no payment provider token, so this works out of the box for any bot.
"""

from __future__ import annotations

import logging

from telegram import LabeledPrice, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
)

from bot.context import BotContext
from bot.handlers.common import reply_or_edit
from bot.keyboards import inline
from bot.keyboards.callbacks import pattern, unpack

logger = logging.getLogger(__name__)

CURRENCY = "XTR"
PAYLOAD_PREFIX = "donation"


def make_payload(user_id: int, amount: int) -> str:
    return f"{PAYLOAD_PREFIX}:{user_id}:{amount}"


def parse_payload(payload: str) -> tuple[int, int] | None:
    """Return ``(user_id, amount)`` for a payload created by :func:`make_payload`."""
    parts = payload.split(":")
    if len(parts) != 3 or parts[0] != PAYLOAD_PREFIX or not all(p.isdigit() for p in parts[1:]):
        return None
    return int(parts[1]), int(parts[2])


async def donate_menu(update: Update, context: BotContext) -> None:
    await reply_or_edit(update, context.t("donate.choose"), inline.donate_menu(context.lang))


async def donate_callback(update: Update, context: BotContext) -> None:
    query, chat = update.callback_query, update.effective_chat
    assert query is not None and chat is not None
    match unpack(query.data):
        case ["donate", "menu"]:
            await donate_menu(update, context)
        case ["donate", amount] if amount.isdigit() and int(amount) in inline.DONATION_AMOUNTS:
            await query.answer()
            await context.bot.send_invoice(
                chat.id,
                title=context.t("donate.title"),
                description=context.t("donate.description"),
                payload=make_payload(query.from_user.id, int(amount)),
                currency=CURRENCY,
                prices=[LabeledPrice(context.t("donate.label"), int(amount))],
            )
        case _:
            await query.answer()


async def pre_checkout(update: Update, context: BotContext) -> None:
    """Telegram asks the bot to confirm the order; we must answer within 10 seconds."""
    query = update.pre_checkout_query
    assert query is not None
    parsed = parse_payload(query.invoice_payload)
    valid = (
        parsed is not None
        and query.currency == CURRENCY
        and parsed == (query.from_user.id, query.total_amount)
    )
    if valid:
        await query.answer(ok=True)
    else:
        await query.answer(ok=False, error_message=context.t("donate.invalid"))


async def successful_payment(update: Update, context: BotContext) -> None:
    message, user = update.effective_message, update.effective_user
    assert message is not None and message.successful_payment is not None and user is not None
    payment = message.successful_payment
    await context.services.payments.add(
        user.id, payment.total_amount, payment.currency, payment.telegram_payment_charge_id
    )
    logger.info("Received %s %s from %s", payment.total_amount, payment.currency, user.id)
    await message.reply_text(context.t("donate.thanks", amount=payment.total_amount))


def register(app: Application) -> None:
    app.add_handlers(
        [
            CommandHandler("donate", donate_menu),
            CallbackQueryHandler(donate_callback, pattern=pattern("donate")),
            PreCheckoutQueryHandler(pre_checkout),
            MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment),
        ]
    )
