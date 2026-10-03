"""Command registry: drives the Telegram command menu and the /help text."""

from __future__ import annotations

import logging

from telegram import Bot, BotCommand, BotCommandScopeChat, BotCommandScopeDefault
from telegram.error import TelegramError

from bot.config import Settings
from bot.i18n import i18n, t

logger = logging.getLogger(__name__)

PUBLIC_COMMANDS: tuple[str, ...] = (
    "start",
    "menu",
    "help",
    "catalog",
    "feedback",
    "media",
    "photo",
    "dice",
    "poll",
    "quiz",
    "remind",
    "reminders",
    "countdown",
    "typing",
    "selfdestruct",
    "invite",
    "donate",
    "settings",
    "cancel",
)
ADMIN_COMMANDS: tuple[str, ...] = ("stats", "broadcast")


def bot_commands(lang: str, admin: bool = False) -> list[BotCommand]:
    names = PUBLIC_COMMANDS + (ADMIN_COMMANDS if admin else ())
    return [BotCommand(name, t(f"cmd.{name}", lang)) for name in names]


def help_text(lang: str, admin: bool = False) -> str:
    lines = [t("help.title", lang), ""]
    lines += [f"/{name} — {t(f'cmd.{name}', lang)}" for name in PUBLIC_COMMANDS]
    if admin:
        lines += ["", t("help.admin_title", lang)]
        lines += [f"/{name} — {t(f'cmd.{name}', lang)}" for name in ADMIN_COMMANDS]
    lines += ["", t("help.footer", lang)]
    return "\n".join(lines)


async def setup_bot_profile(bot: Bot, settings: Settings) -> None:
    """Publish the command menu and bot descriptions for every supported language.

    * default scope + one localised list per ``language_code``;
    * a chat-scoped list with admin commands for each admin;
    * localised description (shown on the empty chat screen) and short description.
    """
    try:
        await bot.set_my_commands(
            bot_commands(settings.default_language), scope=BotCommandScopeDefault()
        )
        for lang in i18n.languages:
            await bot.set_my_commands(bot_commands(lang), language_code=lang)
            # Descriptions are heavily rate-limited, so only update them when they change.
            description = t("bot.description", lang)
            if (await bot.get_my_description(lang)).description != description:
                await bot.set_my_description(description, language_code=lang)
            short = t("bot.short_description", lang)
            if (await bot.get_my_short_description(lang)).short_description != short:
                await bot.set_my_short_description(short, language_code=lang)
    except TelegramError:
        logger.warning("Could not update the bot profile", exc_info=True)

    for admin_id in settings.admin_ids:
        try:
            await bot.set_my_commands(
                bot_commands(settings.default_language, admin=True),
                scope=BotCommandScopeChat(admin_id),
            )
        except TelegramError as exc:
            # Happens when the admin has never started the bot.
            logger.warning("Could not set admin commands for %s: %s", admin_id, exc)
