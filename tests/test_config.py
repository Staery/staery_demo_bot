import pytest
from pydantic import ValidationError

from bot.config import Settings

TOKEN = "123:ABC"


def make(**kwargs: object) -> Settings:
    return Settings(_env_file=None, telegram_bot_token=TOKEN, **kwargs)  # type: ignore[arg-type]


def test_defaults() -> None:
    settings = make()
    assert settings.mode == "polling"
    assert settings.admin_ids == frozenset()
    assert settings.default_language == "en"
    assert not settings.is_admin(1)
    assert not settings.is_admin(None)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("1, 2,3", {1, 2, 3}), ("42", {42}), ("", set()), ("7;8", {7, 8}), ([5, 6], {5, 6})],
)
def test_admin_ids_parsing(raw: object, expected: set[int]) -> None:
    settings = make(admin_ids=raw)
    assert settings.admin_ids == expected
    assert all(settings.is_admin(admin) for admin in expected)


def test_admin_ids_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADMIN_IDS", "10,20")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TOKEN)
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.admin_ids == {10, 20}
    assert settings.telegram_bot_token.get_secret_value() == TOKEN
    assert TOKEN not in repr(settings), "the token must never be printed"


def test_webhook_requires_url() -> None:
    with pytest.raises(ValidationError, match="WEBHOOK_URL"):
        make(mode="webhook")
    with pytest.raises(ValidationError, match="WEBHOOK_URL"):
        make(mode="webhook", webhook_url="  ")


def test_full_webhook_url() -> None:
    settings = make(mode="webhook", webhook_url="https://bot.example.com/", webhook_path="/tg/")
    assert settings.full_webhook_url == "https://bot.example.com/tg"


def test_invalid_values_are_rejected() -> None:
    with pytest.raises(ValidationError):
        make(default_language="de")
    with pytest.raises(ValidationError):
        make(rate_limit_messages=0)
    with pytest.raises(ValidationError):
        make(admin_ids="abc")
