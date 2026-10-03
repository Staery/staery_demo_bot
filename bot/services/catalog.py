"""Static demo catalogue: useful Python libraries (used for pagination and inline search)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CatalogItem:
    id: int
    emoji: str
    name: str
    url: str
    description: dict[str, str]

    def describe(self, lang: str) -> str:
        return self.description.get(lang) or self.description["en"]


def _item(id_: int, emoji: str, name: str, url: str, en: str, ru: str) -> CatalogItem:
    return CatalogItem(id_, emoji, name, url, {"en": en, "ru": ru})


ITEMS: tuple[CatalogItem, ...] = (
    _item(1, "🤖", "python-telegram-bot", "https://python-telegram-bot.org",
          "Async wrapper for the Telegram Bot API. Powers this bot.",
          "Асинхронная обёртка над Telegram Bot API. На ней работает этот бот."),
    _item(2, "🛠", "aiogram", "https://aiogram.dev",
          "Modern asyncio framework for Telegram bots with routers and FSM.",
          "Современный asyncio-фреймворк для Telegram-ботов с роутерами и FSM."),
    _item(3, "🌐", "httpx", "https://www.python-httpx.org",
          "Fully featured HTTP client with sync and async APIs.",
          "Полнофункциональный HTTP-клиент с синхронным и асинхронным API."),
    _item(4, "🧱", "pydantic", "https://docs.pydantic.dev",
          "Data validation using Python type hints.",
          "Валидация данных на основе аннотаций типов Python."),
    _item(5, "⚡", "FastAPI", "https://fastapi.tiangolo.com",
          "High-performance web framework for building APIs.",
          "Высокопроизводительный веб-фреймворк для создания API."),
    _item(6, "🗄", "SQLAlchemy", "https://www.sqlalchemy.org",
          "SQL toolkit and ORM with async support.",
          "SQL-инструментарий и ORM с поддержкой async."),
    _item(7, "🪶", "aiosqlite", "https://github.com/omnilib/aiosqlite",
          "asyncio bridge to the standard sqlite3 module. Used here for storage.",
          "Мост asyncio к стандартному модулю sqlite3. Используется здесь для хранения."),
    _item(8, "⏰", "APScheduler", "https://apscheduler.readthedocs.io",
          "In-process task scheduler behind the PTB JobQueue.",
          "Планировщик задач, на котором построен JobQueue в PTB."),
    _item(9, "🧪", "pytest", "https://docs.pytest.org",
          "The de-facto standard testing framework.",
          "Стандарт де-факто для тестирования на Python."),
    _item(10, "🧹", "Ruff", "https://docs.astral.sh/ruff",
           "Extremely fast linter and formatter written in Rust.",
           "Очень быстрый линтер и форматтер, написанный на Rust."),
    _item(11, "🦄", "Uvicorn", "https://www.uvicorn.org",
           "Lightning-fast ASGI server.",
           "Очень быстрый ASGI-сервер."),
    _item(12, "🥬", "Celery", "https://docs.celeryq.dev",
           "Distributed task queue.",
           "Распределённая очередь задач."),
    _item(13, "🟥", "redis-py", "https://github.com/redis/redis-py",
           "Redis client with asyncio support.",
           "Клиент Redis с поддержкой asyncio."),
    _item(14, "🖼", "Pillow", "https://python-pillow.org",
           "Image processing library.",
           "Библиотека для обработки изображений."),
    _item(15, "🧩", "Jinja2", "https://jinja.palletsprojects.com",
           "Fast and expressive template engine.",
           "Быстрый и выразительный шаблонизатор."),
    _item(16, "🔢", "NumPy", "https://numpy.org",
           "Fundamental package for scientific computing.",
           "Базовый пакет для научных вычислений."),
    _item(17, "🐼", "pandas", "https://pandas.pydata.org",
           "Data analysis and manipulation tool.",
           "Инструмент для анализа и обработки данных."),
    _item(18, "🎨", "Rich", "https://rich.readthedocs.io",
           "Beautiful formatting in the terminal.",
           "Красивое форматирование в терминале."),
    _item(19, "⌨️", "Typer", "https://typer.tiangolo.com",
           "Build command-line apps from type hints.",
           "Создание CLI-приложений на основе аннотаций типов."),
    _item(20, "🐘", "asyncpg", "https://magicstack.github.io/asyncpg",
           "Fast PostgreSQL client for asyncio.",
           "Быстрый клиент PostgreSQL для asyncio."),
    _item(21, "📦", "uv", "https://docs.astral.sh/uv",
           "Fast Python package and project manager.",
           "Быстрый менеджер пакетов и проектов Python."),
    _item(22, "📝", "loguru", "https://loguru.readthedocs.io",
           "Logging made (stupidly) simple.",
           "Логирование — максимально просто."),
)  # fmt: skip

PER_PAGE = 5
_BY_ID = {item.id: item for item in ITEMS}


def get_item(item_id: int) -> CatalogItem | None:
    return _BY_ID.get(item_id)


def search(query: str, lang: str = "en", limit: int = 20) -> list[CatalogItem]:
    """Case-insensitive search in names and descriptions (name matches first)."""
    needle = query.strip().lower()
    if not needle:
        return list(ITEMS[:limit])
    by_name = [item for item in ITEMS if needle in item.name.lower()]
    by_text = [
        item for item in ITEMS if item not in by_name and needle in item.describe(lang).lower()
    ]
    return (by_name + by_text)[:limit]
