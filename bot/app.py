"""Application factory and entry point (polling or webhook)."""

from __future__ import annotations

import logging
import sys
import time

from pydantic import ValidationError
from telegram import LinkPreviewOptions, Update
from telegram.constants import ParseMode
from telegram.ext import AIORateLimiter, Application, ContextTypes, Defaults
from telegram.request import BaseRequest

from bot import __version__
from bot.commands import setup_bot_profile
from bot.config import Settings, get_settings
from bot.context import SERVICES_KEY, BotContext, Services
from bot.handlers import register_handlers
from bot.handlers.admin import STARTED_AT_KEY
from bot.handlers.reminders import restore_reminders
from bot.logging_setup import setup_logging

logger = logging.getLogger(__name__)


def build_application(settings: Settings, request: BaseRequest | None = None) -> Application:
    """Create a fully wired application. No network calls happen here.

    ``request`` lets tests plug in a fake Bot API transport.
    """
    builder = Application.builder().token(settings.telegram_bot_token.get_secret_value())
    if request is not None:
        builder = builder.request(request)
    application = (
        builder
        .context_types(ContextTypes(context=BotContext))
        .defaults(
            Defaults(
                parse_mode=ParseMode.HTML,
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )
        )
        # Outgoing rate limiter: respects Telegram's flood limits and retries on RetryAfter.
        .rate_limiter(AIORateLimiter(max_retries=3))
        .post_init(on_startup)
        .post_shutdown(on_shutdown)
        .build()
    )
    application.bot_data[SERVICES_KEY] = Services.create(settings)
    register_handlers(application, settings)
    return application


async def on_startup(application: Application) -> None:
    services: Services = application.bot_data[SERVICES_KEY]
    application.bot_data[STARTED_AT_KEY] = time.monotonic()
    await services.db.connect()
    await setup_bot_profile(application.bot, services.settings)
    if application.job_queue is not None:
        await restore_reminders(application.job_queue, services)
    logger.info(
        "Bot @%s v%s started in %s mode",
        application.bot.username,
        __version__,
        services.settings.mode,
    )


async def on_shutdown(application: Application) -> None:
    services: Services = application.bot_data[SERVICES_KEY]
    await services.db.close()
    logger.info("Bot stopped")


def run(settings: Settings) -> None:
    application = build_application(settings)
    if settings.mode == "webhook":
        application.run_webhook(
            listen=settings.webhook_listen,
            port=settings.webhook_port,
            url_path=settings.webhook_path,
            webhook_url=settings.full_webhook_url,
            secret_token=(
                settings.webhook_secret.get_secret_value() if settings.webhook_secret else None
            ),
            allowed_updates=Update.ALL_TYPES,
        )
    else:
        application.run_polling(allowed_updates=Update.ALL_TYPES)


def main() -> None:
    try:
        settings = get_settings()
    except ValidationError as exc:
        setup_logging()
        logger.critical("Invalid configuration (see .env.example):\n%s", exc)
        sys.exit(1)
    setup_logging(settings.log_level)
    run(settings)
