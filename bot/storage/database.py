"""Async SQLite connection with versioned schema migrations."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import aiosqlite

logger = logging.getLogger(__name__)

# Each entry upgrades the schema by one version (tracked in ``PRAGMA user_version``).
# Never edit an applied migration: append a new one instead.
MIGRATIONS: tuple[str, ...] = (
    """
    CREATE TABLE users (
        id            INTEGER PRIMARY KEY,
        username      TEXT,
        first_name    TEXT NOT NULL DEFAULT '',
        language_code TEXT,
        language      TEXT,
        referrer_id   INTEGER REFERENCES users(id),
        is_blocked    INTEGER NOT NULL DEFAULT 0,
        created_at    TEXT NOT NULL,
        last_seen_at  TEXT NOT NULL
    );
    CREATE INDEX idx_users_referrer ON users(referrer_id);

    CREATE TABLE feedback (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER NOT NULL REFERENCES users(id),
        name       TEXT NOT NULL,
        email      TEXT NOT NULL,
        rating     INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
        message    TEXT NOT NULL,
        created_at TEXT NOT NULL
    );

    CREATE TABLE reminders (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER NOT NULL,
        chat_id    INTEGER NOT NULL,
        text       TEXT NOT NULL,
        due_at     TEXT NOT NULL,
        sent       INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    );
    CREATE INDEX idx_reminders_pending ON reminders(sent, due_at);

    CREATE TABLE payments (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER NOT NULL,
        amount     INTEGER NOT NULL,
        currency   TEXT NOT NULL,
        charge_id  TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL
    );
    """,
)


class Database:
    """Owns a single ``aiosqlite`` connection for the lifetime of the bot."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._conn: aiosqlite.Connection | None = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database is not connected; call connect() first")
        return self._conn

    async def connect(self) -> None:
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA foreign_keys = ON")
        if self.path != ":memory:":
            await self._conn.execute("PRAGMA journal_mode = WAL")
        await self.migrate()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def migrate(self) -> int:
        """Apply pending migrations and return the resulting schema version."""
        row = await self.fetchone("PRAGMA user_version")
        version = int(row[0]) if row else 0
        for number, script in enumerate(MIGRATIONS[version:], start=version + 1):
            logger.info("Applying database migration #%d", number)
            await self.conn.executescript(
                f"BEGIN;\n{script}\nPRAGMA user_version = {number};\nCOMMIT;"
            )
        return len(MIGRATIONS)

    async def execute(self, sql: str, params: Iterable[Any] = ()) -> aiosqlite.Cursor:
        cursor = await self.conn.execute(sql, tuple(params))
        await self.conn.commit()
        return cursor

    async def fetchone(self, sql: str, params: Iterable[Any] = ()) -> aiosqlite.Row | None:
        async with self.conn.execute(sql, tuple(params)) as cursor:
            return await cursor.fetchone()

    async def fetchall(self, sql: str, params: Iterable[Any] = ()) -> list[aiosqlite.Row]:
        async with self.conn.execute(sql, tuple(params)) as cursor:
            return list(await cursor.fetchall())

    async def __aenter__(self) -> Database:
        await self.connect()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()
