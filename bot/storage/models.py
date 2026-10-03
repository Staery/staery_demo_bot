"""Plain data objects returned by the repositories."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class UserRecord:
    id: int
    username: str | None
    first_name: str
    language_code: str | None
    language: str | None
    referrer_id: int | None
    is_blocked: bool
    created_at: datetime
    last_seen_at: datetime


@dataclass(frozen=True, slots=True)
class UserStats:
    total: int
    active_24h: int
    blocked: int
    by_language: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FeedbackRecord:
    user_id: int
    name: str
    email: str
    rating: int
    message: str
    id: int | None = None
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ReminderRecord:
    id: int
    user_id: int
    chat_id: int
    text: str
    due_at: datetime
    sent: bool
