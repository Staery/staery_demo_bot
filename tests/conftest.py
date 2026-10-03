from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from telegram.ext import Application

from bot.app import build_application, on_shutdown, on_startup
from bot.config import Settings
from bot.context import SERVICES_KEY, Services
from bot.storage import Database
from tests.fake_telegram import FakeTelegram

ADMIN_ID = 999


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]  # ignore a developer's local .env
        telegram_bot_token="123456:TEST-TOKEN",
        admin_ids=str(ADMIN_ID),
        database_path=tmp_path / "bot.sqlite3",
        rate_limit_messages=50,
        rate_limit_period=1,
    )


@pytest.fixture
async def db(tmp_path: Path) -> AsyncIterator[Database]:
    database = Database(tmp_path / "test.sqlite3")
    await database.connect()
    yield database
    await database.close()


@pytest.fixture
def fake() -> FakeTelegram:
    return FakeTelegram()


@pytest.fixture
async def app(settings: Settings, fake: FakeTelegram) -> AsyncIterator[Application]:
    """A fully wired application talking to the in-memory fake Bot API."""
    application = build_application(settings, request=fake)
    await application.initialize()
    await on_startup(application)
    await application.start()
    fake.reset()
    yield application
    await application.stop()
    await on_shutdown(application)
    await application.shutdown()


@pytest.fixture
def services(app: Application) -> Services:
    return app.bot_data[SERVICES_KEY]
