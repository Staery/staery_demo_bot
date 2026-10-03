"""Application settings loaded from environment variables (and an optional ``.env`` file)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

Language = Literal["en", "ru"]


class Settings(BaseSettings):
    """All runtime configuration of the bot.

    Every field maps to an upper-case environment variable,
    e.g. ``telegram_bot_token`` -> ``TELEGRAM_BOT_TOKEN``.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    telegram_bot_token: SecretStr
    admin_ids: Annotated[frozenset[int], NoDecode] = frozenset()
    default_language: Language = "en"
    database_path: Path = Path("data/bot.sqlite3")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    rate_limit_messages: int = Field(default=6, ge=1)
    rate_limit_period: float = Field(default=4.0, gt=0)

    mode: Literal["polling", "webhook"] = "polling"
    webhook_url: str | None = None
    webhook_path: str = "telegram"
    webhook_secret: SecretStr | None = None
    webhook_listen: str = "0.0.0.0"
    webhook_port: int = Field(default=8080, ge=1, le=65535)

    @field_validator("admin_ids", mode="before")
    @classmethod
    def _parse_admin_ids(cls, value: object) -> object:
        """Accept ``"1, 2,3"`` as well as a real list of integers."""
        if isinstance(value, str):
            return frozenset(
                int(part) for part in value.replace(";", ",").split(",") if part.strip()
            )
        if isinstance(value, int):
            return frozenset({value})
        return value

    @field_validator("webhook_url", "webhook_secret", mode="before")
    @classmethod
    def _empty_to_none(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("webhook_path")
    @classmethod
    def _strip_slashes(cls, value: str) -> str:
        return value.strip("/")

    @model_validator(mode="after")
    def _check_webhook(self) -> Settings:
        if self.mode == "webhook" and not self.webhook_url:
            raise ValueError("WEBHOOK_URL is required when MODE=webhook")
        return self

    @property
    def full_webhook_url(self) -> str:
        """Public URL Telegram should deliver updates to."""
        if not self.webhook_url:
            raise ValueError("WEBHOOK_URL is not configured")
        return f"{self.webhook_url.rstrip('/')}/{self.webhook_path}"

    def is_admin(self, user_id: int | None) -> bool:
        return user_id is not None and user_id in self.admin_ids


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings instance."""
    return Settings()  # type: ignore[call-arg]  # values come from the environment
