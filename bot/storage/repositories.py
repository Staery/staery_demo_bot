"""Repositories: the only place where SQL lives."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import aiosqlite

from bot.storage.database import Database
from bot.storage.models import FeedbackRecord, ReminderRecord, UserRecord, UserStats


def utcnow() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _ts(value: datetime) -> str:
    """Serialise a datetime as a sortable UTC ISO-8601 string."""
    return value.astimezone(UTC).replace(microsecond=0).isoformat()


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


class UserRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    @staticmethod
    def _to_record(row: aiosqlite.Row) -> UserRecord:
        return UserRecord(
            id=row["id"],
            username=row["username"],
            first_name=row["first_name"],
            language_code=row["language_code"],
            language=row["language"],
            referrer_id=row["referrer_id"],
            is_blocked=bool(row["is_blocked"]),
            created_at=_dt(row["created_at"]),
            last_seen_at=_dt(row["last_seen_at"]),
        )

    async def get(self, user_id: int) -> UserRecord | None:
        row = await self.db.fetchone("SELECT * FROM users WHERE id = ?", (user_id,))
        return self._to_record(row) if row else None

    async def upsert(
        self,
        user_id: int,
        first_name: str,
        username: str | None = None,
        language_code: str | None = None,
        now: datetime | None = None,
    ) -> tuple[UserRecord, bool]:
        """Create or refresh a user. Returns ``(record, created)``.

        Seeing a message from a user also means they have not blocked the bot (any more).
        """
        stamp = _ts(now or utcnow())
        created = await self.get(user_id) is None
        await self.db.execute(
            """
            INSERT INTO users (id, username, first_name, language_code, created_at, last_seen_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                language_code = excluded.language_code,
                last_seen_at = excluded.last_seen_at,
                is_blocked = 0
            """,
            (user_id, username, first_name or "", language_code, stamp, stamp),
        )
        record = await self.get(user_id)
        assert record is not None
        return record, created

    async def set_language(self, user_id: int, language: str | None) -> None:
        await self.db.execute("UPDATE users SET language = ? WHERE id = ?", (language, user_id))

    async def set_blocked(self, user_id: int, blocked: bool) -> None:
        await self.db.execute(
            "UPDATE users SET is_blocked = ? WHERE id = ?", (int(blocked), user_id)
        )

    async def set_referrer(self, user_id: int, referrer_id: int) -> bool:
        """Attach a referrer once. Self-referrals and unknown referrers are ignored."""
        if user_id == referrer_id or await self.get(referrer_id) is None:
            return False
        cursor = await self.db.execute(
            "UPDATE users SET referrer_id = ? WHERE id = ? AND referrer_id IS NULL",
            (referrer_id, user_id),
        )
        return cursor.rowcount == 1

    async def count_referrals(self, user_id: int) -> int:
        row = await self.db.fetchone("SELECT COUNT(*) FROM users WHERE referrer_id = ?", (user_id,))
        return int(row[0]) if row else 0

    async def active_ids(self) -> list[int]:
        """IDs of users who have not blocked the bot (broadcast recipients)."""
        rows = await self.db.fetchall("SELECT id FROM users WHERE is_blocked = 0 ORDER BY id")
        return [row["id"] for row in rows]

    async def stats(self, now: datetime | None = None) -> UserStats:
        since = _ts((now or utcnow()) - timedelta(hours=24))
        row = await self.db.fetchone(
            """
            SELECT COUNT(*)                                          AS total,
                   COALESCE(SUM(last_seen_at >= ?), 0)               AS active,
                   COALESCE(SUM(is_blocked), 0)                      AS blocked
            FROM users
            """,
            (since,),
        )
        languages = await self.db.fetchall(
            """
            SELECT COALESCE(language, language_code, '?') AS lang, COUNT(*) AS n
            FROM users GROUP BY lang ORDER BY n DESC, lang
            """
        )
        assert row is not None
        return UserStats(
            total=row["total"],
            active_24h=row["active"],
            blocked=row["blocked"],
            by_language={r["lang"]: r["n"] for r in languages},
        )


class FeedbackRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def add(self, feedback: FeedbackRecord, now: datetime | None = None) -> int:
        cursor = await self.db.execute(
            """
            INSERT INTO feedback (user_id, name, email, rating, message, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                feedback.user_id,
                feedback.name,
                feedback.email,
                feedback.rating,
                feedback.message,
                _ts(now or utcnow()),
            ),
        )
        assert cursor.lastrowid is not None
        return cursor.lastrowid

    async def count_and_average(self) -> tuple[int, float | None]:
        row = await self.db.fetchone("SELECT COUNT(*), AVG(rating) FROM feedback")
        assert row is not None
        return int(row[0]), (round(float(row[1]), 2) if row[1] is not None else None)

    async def latest(self, limit: int = 5) -> list[FeedbackRecord]:
        rows = await self.db.fetchall("SELECT * FROM feedback ORDER BY id DESC LIMIT ?", (limit,))
        return [
            FeedbackRecord(
                id=r["id"],
                user_id=r["user_id"],
                name=r["name"],
                email=r["email"],
                rating=r["rating"],
                message=r["message"],
                created_at=_dt(r["created_at"]),
            )
            for r in rows
        ]


class ReminderRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    @staticmethod
    def _to_record(row: aiosqlite.Row) -> ReminderRecord:
        return ReminderRecord(
            id=row["id"],
            user_id=row["user_id"],
            chat_id=row["chat_id"],
            text=row["text"],
            due_at=_dt(row["due_at"]),
            sent=bool(row["sent"]),
        )

    async def add(self, user_id: int, chat_id: int, text: str, due_at: datetime) -> ReminderRecord:
        cursor = await self.db.execute(
            """
            INSERT INTO reminders (user_id, chat_id, text, due_at, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, chat_id, text, _ts(due_at), _ts(utcnow())),
        )
        assert cursor.lastrowid is not None
        record = await self.get(cursor.lastrowid)
        assert record is not None
        return record

    async def get(self, reminder_id: int) -> ReminderRecord | None:
        row = await self.db.fetchone("SELECT * FROM reminders WHERE id = ?", (reminder_id,))
        return self._to_record(row) if row else None

    async def pending(self, user_id: int | None = None) -> list[ReminderRecord]:
        """Unsent reminders ordered by due time, optionally for a single user."""
        if user_id is None:
            rows = await self.db.fetchall(
                "SELECT * FROM reminders WHERE sent = 0 ORDER BY due_at, id"
            )
        else:
            rows = await self.db.fetchall(
                "SELECT * FROM reminders WHERE sent = 0 AND user_id = ? ORDER BY due_at, id",
                (user_id,),
            )
        return [self._to_record(r) for r in rows]

    async def mark_sent(self, reminder_id: int) -> None:
        await self.db.execute("UPDATE reminders SET sent = 1 WHERE id = ?", (reminder_id,))

    async def delete(self, reminder_id: int, user_id: int) -> bool:
        """Delete a pending reminder owned by ``user_id``."""
        cursor = await self.db.execute(
            "DELETE FROM reminders WHERE id = ? AND user_id = ? AND sent = 0",
            (reminder_id, user_id),
        )
        return cursor.rowcount == 1


class PaymentRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def add(self, user_id: int, amount: int, currency: str, charge_id: str) -> None:
        await self.db.execute(
            """
            INSERT OR IGNORE INTO payments (user_id, amount, currency, charge_id, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, amount, currency, charge_id, _ts(utcnow())),
        )

    async def total(self, currency: str = "XTR") -> int:
        row = await self.db.fetchone(
            "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE currency = ?", (currency,)
        )
        return int(row[0]) if row else 0
