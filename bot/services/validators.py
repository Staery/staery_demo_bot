"""Validators for the feedback conversation. Each returns a normalised value or raises."""

from __future__ import annotations

import re

NAME_MIN, NAME_MAX = 2, 64
MESSAGE_MIN, MESSAGE_MAX = 10, 1000
EMAIL_MAX = 254

_NAME_RE = re.compile(r"[^\W\d_]+(?:[ '.\-][^\W\d_]+)*\.?")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@(?:[A-Za-z0-9\-]+\.)+[A-Za-z]{2,}")


class ValidationError(ValueError):
    """``key`` is the i18n key of the user-facing error message."""

    def __init__(self, key: str, **params: object) -> None:
        super().__init__(key)
        self.key = key
        self.params = params


def _collapse_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def validate_name(text: str) -> str:
    name = _collapse_spaces(text)
    if not NAME_MIN <= len(name) <= NAME_MAX:
        raise ValidationError("feedback.err_name_length", min=NAME_MIN, max=NAME_MAX)
    if not _NAME_RE.fullmatch(name):
        raise ValidationError("feedback.err_name_chars")
    return name


def validate_email(text: str) -> str:
    email = text.strip()
    if len(email) > EMAIL_MAX or not _EMAIL_RE.fullmatch(email):
        raise ValidationError("feedback.err_email")
    local, domain = email.rsplit("@", 1)
    return f"{local}@{domain.lower()}"


def validate_rating(value: str | int) -> int:
    """Accept ``4``, ``"4"`` or ``"⭐⭐⭐⭐"``."""
    if isinstance(value, str):
        stripped = value.strip()
        if stripped and set(stripped) == {"⭐"}:
            value = len(stripped)
        elif stripped.isdigit():
            value = int(stripped)
        else:
            raise ValidationError("feedback.err_rating")
    if not 1 <= value <= 5:
        raise ValidationError("feedback.err_rating")
    return value


def validate_message(text: str) -> str:
    message = text.strip()
    if len(message) < MESSAGE_MIN:
        raise ValidationError("feedback.err_message_short", min=MESSAGE_MIN)
    if len(message) > MESSAGE_MAX:
        raise ValidationError("feedback.err_message_long", max=MESSAGE_MAX)
    return message
