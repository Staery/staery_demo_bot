"""An in-memory stand-in for the Telegram Bot API.

``FakeTelegram`` plugs into python-telegram-bot as its HTTP transport, records every API
call and returns plausible responses, so whole update flows can be tested offline.
"""

from __future__ import annotations

import itertools
import json
from typing import Any

from telegram import Bot, Update
from telegram.request import BaseRequest, RequestData

BOT_ID = 123456
BOT_USERNAME = "staery_demo_bot"
BOT_USER = {
    "id": BOT_ID,
    "is_bot": True,
    "first_name": "Demo",
    "username": BOT_USERNAME,
    "can_join_groups": True,
    "can_read_all_group_messages": False,
    "supports_inline_queries": True,
}


class FakeTelegram(BaseRequest):
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._ids = itertools.count(1000)

    async def initialize(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    @property
    def read_timeout(self) -> float:
        return 1.0

    async def do_request(
        self, url: str, method: str, request_data: RequestData | None = None, **_: Any
    ) -> tuple[int, bytes]:
        api_method = url.rsplit("/", 1)[-1]
        params = dict(request_data.parameters) if request_data else {}
        self.calls.append((api_method, params))
        body = {"ok": True, "result": self._result(api_method, params)}
        return 200, json.dumps(body).encode()

    # ------------------------------------------------------------------ helpers for tests

    def methods(self) -> list[str]:
        return [name for name, _ in self.calls]

    def find(self, method: str) -> list[dict[str, Any]]:
        return [params for name, params in self.calls if name == method]

    def texts(self, method: str = "sendMessage") -> list[str]:
        return [str(params.get("text", "")) for params in self.find(method)]

    def reset(self) -> None:
        self.calls.clear()

    # ------------------------------------------------------------------ responses

    def _message(self, params: dict[str, Any], **extra: Any) -> dict[str, Any]:
        chat_id = params.get("chat_id", 1)
        message = {
            "message_id": params.get("message_id") or next(self._ids),
            "date": 0,
            "chat": {"id": chat_id, "type": "private" if int(chat_id) > 0 else "group"},
            "from": BOT_USER,
        }
        if "text" in params:
            message["text"] = params["text"]
        message.update(extra)
        return message

    def _result(self, method: str, params: dict[str, Any]) -> Any:
        if method == "getMe":
            return BOT_USER
        if method == "getMyDescription":
            return {"description": ""}
        if method == "getMyShortDescription":
            return {"short_description": ""}
        if method == "sendPoll":
            options = params.get("options", [])
            poll = {
                "id": str(next(self._ids)),
                "question": params.get("question", ""),
                "options": [
                    {
                        "persistent_id": str(index),
                        "text": option["text"] if isinstance(option, dict) else option,
                        "voter_count": 0,
                    }
                    for index, option in enumerate(options)
                ],
                "total_voter_count": 0,
                "is_closed": False,
                "is_anonymous": params.get("is_anonymous", True),
                "type": params.get("type", "regular"),
                "allows_multiple_answers": False,
                "allows_revoting": True,
                "members_only": False,
            }
            return self._message(params, poll=poll)
        if method == "sendDice":
            return self._message(params, dice={"emoji": params.get("emoji", "🎲"), "value": 4})
        if method == "sendMediaGroup":
            return [self._message(params) for _ in params.get("media", [])]
        if method.startswith(("send", "copy", "edit")) and method != "sendChatAction":
            if method.startswith("copy"):
                return {"message_id": next(self._ids)}
            return self._message(params)
        return True


# ---------------------------------------------------------------------- update builders

_update_ids = itertools.count(1)


def user_dict(user_id: int = 1, language_code: str = "en", first_name: str = "Ann") -> dict:
    return {
        "id": user_id,
        "is_bot": False,
        "first_name": first_name,
        "username": f"user{user_id}",
        "language_code": language_code,
    }


def message_update(
    bot: Bot,
    text: str | None = None,
    *,
    user_id: int = 1,
    chat_id: int | None = None,
    language_code: str = "en",
    **extra: Any,
) -> Update:
    message: dict[str, Any] = {
        "message_id": next(_update_ids),
        "date": 0,
        "chat": {"id": chat_id or user_id, "type": "private" if chat_id is None else "group"},
        "from": user_dict(user_id, language_code),
    }
    if text is not None:
        message["text"] = text
        if text.startswith("/"):
            command = text.split()[0]
            message["entities"] = [{"type": "bot_command", "offset": 0, "length": len(command)}]
    message.update(extra)
    return Update.de_json({"update_id": next(_update_ids), "message": message}, bot)


def callback_update(
    bot: Bot, data: str, *, user_id: int = 1, language_code: str = "en", text: str = "x"
) -> Update:
    return Update.de_json(
        {
            "update_id": next(_update_ids),
            "callback_query": {
                "id": str(next(_update_ids)),
                "from": user_dict(user_id, language_code),
                "chat_instance": "ci",
                "data": data,
                "message": {
                    "message_id": 77,
                    "date": 0,
                    "chat": {"id": user_id, "type": "private"},
                    "from": BOT_USER,
                    "text": text,
                },
            },
        },
        bot,
    )


def inline_query_update(bot: Bot, query: str, *, user_id: int = 1) -> Update:
    return Update.de_json(
        {
            "update_id": next(_update_ids),
            "inline_query": {
                "id": str(next(_update_ids)),
                "from": user_dict(user_id),
                "query": query,
                "offset": "",
            },
        },
        bot,
    )


def pre_checkout_update(
    bot: Bot, payload: str, amount: int, *, user_id: int = 1, currency: str = "XTR"
) -> Update:
    return Update.de_json(
        {
            "update_id": next(_update_ids),
            "pre_checkout_query": {
                "id": str(next(_update_ids)),
                "from": user_dict(user_id),
                "currency": currency,
                "total_amount": amount,
                "invoice_payload": payload,
            },
        },
        bot,
    )
