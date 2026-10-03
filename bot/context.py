"""Custom callback context and the service container shared by all handlers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from telegram.ext import CallbackContext, ExtBot

from bot.config import Settings
from bot.i18n import i18n
from bot.services.rate_limiter import SlidingWindowRateLimiter
from bot.storage import (
    Database,
    FeedbackRepository,
    PaymentRepository,
    ReminderRepository,
    UserRepository,
)

SERVICES_KEY = "services"
LANG_KEY = "lang"


@dataclass(slots=True)
class Services:
    """Dependencies created once at startup and stored in ``application.bot_data``."""

    settings: Settings
    db: Database
    users: UserRepository
    feedback: FeedbackRepository
    reminders: ReminderRepository
    payments: PaymentRepository
    rate_limiter: SlidingWindowRateLimiter

    @classmethod
    def create(cls, settings: Settings) -> Services:
        db = Database(settings.database_path)
        return cls(
            settings=settings,
            db=db,
            users=UserRepository(db),
            feedback=FeedbackRepository(db),
            reminders=ReminderRepository(db),
            payments=PaymentRepository(db),
            rate_limiter=SlidingWindowRateLimiter(
                limit=settings.rate_limit_messages, period=settings.rate_limit_period
            ),
        )

    async def language_for(self, user_id: int) -> str:
        """Language of a user outside of an update (jobs, broadcasts)."""
        user = await self.users.get(user_id)
        if user is None:
            return self.settings.default_language
        return i18n.resolve(user.language, user.language_code, self.settings.default_language)


class BotContext(CallbackContext[ExtBot[None], dict[Any, Any], dict[Any, Any], dict[Any, Any]]):
    """``CallbackContext`` with typed shortcuts: ``context.services``, ``context.t(...)``."""

    @property
    def services(self) -> Services:
        return self.bot_data[SERVICES_KEY]

    @property
    def settings(self) -> Settings:
        return self.services.settings

    @property
    def lang(self) -> str:
        """Language resolved by the user-tracking middleware for the current user."""
        if self.user_data is not None and LANG_KEY in self.user_data:
            return self.user_data[LANG_KEY]
        return self.settings.default_language

    def t(self, key: str, /, **kwargs: object) -> str:
        """Translate ``key`` into the current user's language."""
        return i18n.get(key, self.lang, **kwargs)
