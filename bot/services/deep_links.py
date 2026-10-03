"""Parsing of ``/start`` deep-link payloads (``https://t.me/<bot>?start=<payload>``)."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from telegram.helpers import create_deep_linked_url


class PayloadKind(StrEnum):
    NONE = "none"
    REFERRAL = "ref"
    ITEM = "item"
    FEEDBACK = "feedback"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class StartPayload:
    kind: PayloadKind
    value: int | None = None
    raw: str = ""


_PAYLOAD_RE = re.compile(r"^(?P<kind>ref|item)_(?P<value>\d{1,19})$")


def parse_start_payload(args: Sequence[str] | None) -> StartPayload:
    """Turn ``context.args`` of a ``/start`` command into a typed payload."""
    if not args:
        return StartPayload(PayloadKind.NONE)
    raw = args[0].strip()
    if raw == "feedback":
        return StartPayload(PayloadKind.FEEDBACK, raw=raw)
    match = _PAYLOAD_RE.match(raw)
    if not match:
        return StartPayload(PayloadKind.UNKNOWN, raw=raw)
    return StartPayload(PayloadKind(match["kind"]), int(match["value"]), raw)


def referral_link(bot_username: str, user_id: int) -> str:
    return create_deep_linked_url(bot_username, f"ref_{user_id}")


def item_link(bot_username: str, item_id: int) -> str:
    return create_deep_linked_url(bot_username, f"item_{item_id}")


def feedback_link(bot_username: str) -> str:
    return create_deep_linked_url(bot_username, "feedback")
