"""Tiny dictionary-based internationalisation.

Translations live in ``locales/<lang>.json`` as flat ``"dotted.key": "text"`` maps.
Texts are ``str.format`` templates, so ``t("start.welcome", "en", name="Ann")`` fills ``{name}``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

LOCALES_DIR = Path(__file__).parent / "locales"


class Translator:
    def __init__(self, translations: Mapping[str, Mapping[str, str]], default: str = "en") -> None:
        if default not in translations:
            raise ValueError(f"Default language {default!r} has no translations")
        self._translations = translations
        self.default = default

    @classmethod
    def from_directory(cls, path: Path = LOCALES_DIR, default: str = "en") -> Translator:
        translations = {
            file.stem: json.loads(file.read_text(encoding="utf-8"))
            for file in sorted(path.glob("*.json"))
        }
        return cls(translations, default=default)

    @property
    def languages(self) -> tuple[str, ...]:
        return tuple(self._translations)

    def get(self, key: str, lang: str | None = None, /, **kwargs: object) -> str:
        """Translate ``key`` into ``lang``; fall back to the default language, then to the key."""
        template = self._translations.get(lang or self.default, {}).get(key)
        if template is None:
            template = self._translations[self.default].get(key, key)
        return template.format(**kwargs) if kwargs else template

    def variants(self, key: str) -> tuple[str, ...]:
        """All translations of ``key`` (useful to match localised reply-keyboard buttons)."""
        return tuple(dict.fromkeys(t[key] for t in self._translations.values() if key in t))

    def resolve(self, preferred: str | None, telegram_code: str | None, fallback: str) -> str:
        """Pick the language for a user.

        1. the language explicitly chosen in /settings,
        2. the language of the Telegram client (``ru-RU`` -> ``ru``),
        3. the configured fallback.
        """
        if preferred in self._translations:
            return preferred  # type: ignore[return-value]
        if telegram_code:
            short = telegram_code.split("-")[0].lower()
            if short in self._translations:
                return short
        return fallback if fallback in self._translations else self.default

    def missing_keys(self) -> dict[str, set[str]]:
        """Keys present in the default language but missing elsewhere (used by tests)."""
        reference = set(self._translations[self.default])
        return {
            lang: reference - set(texts)
            for lang, texts in self._translations.items()
            if reference - set(texts)
        }


i18n = Translator.from_directory()


def t(key: str, lang: str | None = None, /, **kwargs: object) -> str:
    """Shortcut for :meth:`Translator.get` on the global translator."""
    return i18n.get(key, lang, **kwargs)
