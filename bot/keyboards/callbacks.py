"""Callback-data helpers.

Callback data is limited to 64 bytes, so a compact ``feature:action:arg`` scheme is used,
e.g. ``catalog:page:2`` or ``settings:lang:ru``.
"""

from __future__ import annotations

import re

SEPARATOR = ":"
MAX_CALLBACK_BYTES = 64


def pack(*parts: object) -> str:
    """Join parts into callback data, validating Telegram's 64-byte limit."""
    data = SEPARATOR.join(str(part) for part in parts)
    if len(data.encode("utf-8")) > MAX_CALLBACK_BYTES:
        raise ValueError(f"Callback data is longer than {MAX_CALLBACK_BYTES} bytes: {data!r}")
    return data


def unpack(data: str | None) -> list[str]:
    return data.split(SEPARATOR) if data else []


def pattern(prefix: str, action: str | None = None) -> str:
    """Regex for ``CallbackQueryHandler(pattern=...)`` matching a prefix and optional action."""
    head = re.escape(prefix) + (SEPARATOR + re.escape(action) if action else "")
    return rf"^{head}(?:{SEPARATOR}|$)"
