import re
from pathlib import Path

import pytest

from bot.i18n import Translator, i18n, t

BOT_DIR = Path(__file__).resolve().parents[1] / "bot"
PLACEHOLDER = re.compile(r"\{(\w+)\}")


@pytest.fixture
def translator() -> Translator:
    return Translator(
        {
            "en": {"hello": "Hello, {name}!", "only_en": "English only", "btn": "Go"},
            "ru": {"hello": "Привет, {name}!", "btn": "Вперёд"},
        }
    )


def test_lookup_with_formatting(translator: Translator) -> None:
    assert translator.get("hello", "ru", name="Аня") == "Привет, Аня!"
    assert translator.get("hello", "en", name="Ann") == "Hello, Ann!"


def test_fallback_to_default_language_and_key(translator: Translator) -> None:
    assert translator.get("only_en", "ru") == "English only"
    assert translator.get("only_en", "de") == "English only"
    assert translator.get("missing.key", "ru") == "missing.key"


def test_variants_are_unique(translator: Translator) -> None:
    assert translator.variants("btn") == ("Go", "Вперёд")


@pytest.mark.parametrize(
    ("preferred", "telegram_code", "fallback", "expected"),
    [
        ("ru", "en", "en", "ru"),
        (None, "ru", "en", "ru"),
        (None, "ru-RU", "en", "ru"),
        (None, "de", "en", "en"),
        (None, None, "ru", "ru"),
        ("xx", None, "zz", "en"),
    ],
)
def test_resolve(
    translator: Translator,
    preferred: str | None,
    telegram_code: str | None,
    fallback: str,
    expected: str,
) -> None:
    assert translator.resolve(preferred, telegram_code, fallback) == expected


def test_unknown_default_language_is_rejected() -> None:
    with pytest.raises(ValueError, match="Default language"):
        Translator({"ru": {}}, default="en")


def test_bundled_locales_are_complete() -> None:
    assert set(i18n.languages) == {"en", "ru"}
    assert i18n.missing_keys() == {}


def test_placeholders_match_across_languages() -> None:
    for key in i18n._translations["en"]:
        en_vars = set(PLACEHOLDER.findall(t(key, "en")))
        ru_vars = set(PLACEHOLDER.findall(t(key, "ru")))
        assert en_vars == ru_vars, key


def test_every_key_used_in_code_exists() -> None:
    source = "\n".join(path.read_text(encoding="utf-8") for path in BOT_DIR.rglob("*.py"))
    used = set(re.findall(r"""(?:t|ValidationError)\(\s*["']([a-z_]+\.[a-z_.0-9]+)["']""", source))
    used |= set(re.findall(r"""button_filter\(["']([a-z_.]+)["']\)""", source))
    assert used, "the regex should find keys"
    missing = {key for key in used if t(key, "en") == key}
    assert missing == set()


def test_command_descriptions_fit_telegram_limits() -> None:
    from bot.commands import ADMIN_COMMANDS, PUBLIC_COMMANDS

    for lang in i18n.languages:
        for name in PUBLIC_COMMANDS + ADMIN_COMMANDS:
            assert re.fullmatch(r"[a-z0-9_]{1,32}", name)
            assert 1 <= len(t(f"cmd.{name}", lang)) <= 256
        assert len(t("bot.description", lang)) <= 512
        assert len(t("bot.short_description", lang)) <= 120
