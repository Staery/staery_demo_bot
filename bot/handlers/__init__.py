"""Handler registration. The order matters: within a group the first matching handler wins."""

from __future__ import annotations

from telegram.ext import Application

from bot import middlewares
from bot.config import Settings
from bot.handlers import (
    admin,
    catalog,
    effects,
    errors,
    fallback,
    feedback,
    groups,
    inline_mode,
    media,
    payments,
    reminders,
    settings,
    start,
)


def register_handlers(app: Application, config: Settings) -> None:
    middlewares.register(app)

    # The feedback conversation goes first: it owns "/start feedback" and the form steps.
    feedback.register(app)
    start.register(app)
    admin.register(app, config.admin_ids)
    catalog.register(app)
    settings.register(app)
    media.register(app)
    effects.register(app)
    reminders.register(app)
    payments.register(app)
    inline_mode.register(app)
    groups.register(app)
    fallback.register(app)  # must stay last

    app.add_error_handler(errors.error_handler)
