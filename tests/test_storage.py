from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from bot.storage import (
    Database,
    FeedbackRecord,
    FeedbackRepository,
    PaymentRepository,
    ReminderRepository,
    UserRepository,
)
from bot.storage.database import MIGRATIONS


async def test_migrations_are_applied_once(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "dir" / "bot.sqlite3"
    async with Database(path) as db:
        row = await db.fetchone("PRAGMA user_version")
        assert row is not None
        assert row[0] == len(MIGRATIONS)
    # Re-opening an existing database must not fail or re-run migrations.
    async with Database(path) as db:
        assert await db.migrate() == len(MIGRATIONS)
    assert path.exists()


async def test_in_memory_database() -> None:
    async with Database(":memory:") as db:
        assert await UserRepository(db).get(1) is None


async def test_using_closed_database_raises(tmp_path: Path) -> None:
    db = Database(tmp_path / "x.sqlite3")
    with pytest.raises(RuntimeError, match="not connected"):
        _ = db.conn


async def test_user_upsert_and_get(db: Database) -> None:
    users = UserRepository(db)
    record, created = await users.upsert(1, "Ann", "ann", "en")
    assert created
    assert (record.id, record.first_name, record.username, record.language_code) == (
        1,
        "Ann",
        "ann",
        "en",
    )
    assert record.language is None
    assert not record.is_blocked

    record, created = await users.upsert(1, "Anna", None, "ru")
    assert not created
    assert (record.first_name, record.username, record.language_code) == ("Anna", None, "ru")


async def test_language_and_block_flags(db: Database) -> None:
    users = UserRepository(db)
    await users.upsert(1, "Ann")
    await users.set_language(1, "ru")
    await users.set_blocked(1, True)
    record = await users.get(1)
    assert record is not None
    assert record.language == "ru"
    assert record.is_blocked
    assert await users.active_ids() == []

    # Any new activity means the user has unblocked the bot.
    await users.upsert(1, "Ann")
    assert await users.active_ids() == [1]


async def test_referrals(db: Database) -> None:
    users = UserRepository(db)
    for user_id in (1, 2, 3):
        await users.upsert(user_id, f"U{user_id}")

    assert await users.set_referrer(2, 1)
    assert not await users.set_referrer(2, 3), "a referrer is set only once"
    assert not await users.set_referrer(3, 3), "self-referral is ignored"
    assert not await users.set_referrer(3, 404), "unknown referrer is ignored"
    assert await users.set_referrer(3, 1)
    assert await users.count_referrals(1) == 2
    assert await users.count_referrals(2) == 0


async def test_user_stats(db: Database) -> None:
    users = UserRepository(db)
    now = datetime(2026, 1, 10, 12, tzinfo=UTC)
    await users.upsert(1, "A", language_code="en", now=now)
    await users.upsert(2, "B", language_code="ru", now=now - timedelta(hours=1))
    await users.upsert(3, "C", language_code="ru", now=now - timedelta(days=3))
    await users.set_language(1, "ru")
    await users.set_blocked(3, True)

    stats = await users.stats(now=now)
    assert stats.total == 3
    assert stats.active_24h == 2
    assert stats.blocked == 1
    assert stats.by_language == {"ru": 3}


async def test_feedback(db: Database) -> None:
    await UserRepository(db).upsert(1, "Ann")
    feedback = FeedbackRepository(db)
    assert await feedback.count_and_average() == (0, None)

    first = await feedback.add(FeedbackRecord(1, "Ann", "a@b.io", 5, "Great bot, thanks!"))
    second = await feedback.add(FeedbackRecord(1, "Ann", "", 2, "Could be better."))
    assert second == first + 1
    assert await feedback.count_and_average() == (2, 3.5)

    latest = await feedback.latest(1)
    assert [item.rating for item in latest] == [2]
    assert latest[0].created_at is not None


async def test_feedback_rating_constraint(db: Database) -> None:
    await UserRepository(db).upsert(1, "Ann")
    with pytest.raises(Exception, match="CHECK constraint"):
        await FeedbackRepository(db).add(FeedbackRecord(1, "Ann", "", 9, "Out of range!"))


async def test_reminders_lifecycle(db: Database) -> None:
    reminders = ReminderRepository(db)
    due = datetime(2030, 5, 1, 9, 30, tzinfo=UTC)
    later = await reminders.add(1, 10, "later", due + timedelta(hours=1))
    sooner = await reminders.add(1, 10, "sooner", due)
    other = await reminders.add(2, 20, "other user", due)

    assert sooner.due_at == due
    assert not sooner.sent
    assert [r.text for r in await reminders.pending(1)] == ["sooner", "later"]
    assert len(await reminders.pending()) == 3

    await reminders.mark_sent(sooner.id)
    assert [r.id for r in await reminders.pending(1)] == [later.id]

    assert not await reminders.delete(other.id, user_id=1), "cannot delete someone else's"
    assert await reminders.delete(later.id, user_id=1)
    assert not await reminders.delete(sooner.id, user_id=1), "sent reminders stay in history"
    assert await reminders.pending(1) == []
    assert await reminders.get(404) is None


async def test_payments_are_idempotent(db: Database) -> None:
    payments = PaymentRepository(db)
    await payments.add(1, 10, "XTR", "charge-1")
    await payments.add(1, 10, "XTR", "charge-1")  # Telegram may deliver an update twice
    await payments.add(2, 5, "XTR", "charge-2")
    await payments.add(2, 100, "USD", "charge-3")
    assert await payments.total("XTR") == 15
    assert await payments.total("USD") == 100
