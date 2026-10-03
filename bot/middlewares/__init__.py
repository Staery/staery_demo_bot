"""Pre-processing "middlewares".

python-telegram-bot runs handler groups in ascending order, so ``TypeHandler(Update, ...)``
in negative groups acts like middleware: it sees every update before the feature handlers
and can stop processing by raising ``ApplicationHandlerStop``.
"""

from telegram import Update
from telegram.ext import Application, TypeHandler

from bot.middlewares.anti_flood import anti_flood
from bot.middlewares.user_tracking import track_user

ANTI_FLOOD_GROUP = -2
USER_TRACKING_GROUP = -1


def register(app: Application) -> None:
    app.add_handler(TypeHandler(Update, anti_flood), group=ANTI_FLOOD_GROUP)
    app.add_handler(TypeHandler(Update, track_user), group=USER_TRACKING_GROUP)


__all__ = ["anti_flood", "register", "track_user"]
