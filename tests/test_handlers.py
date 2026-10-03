"""End-to-end update flows against the in-memory fake Bot API (no network access)."""

from __future__ import annotations

import asyncio

import pytest
from telegram import Update
from telegram.ext import Application, CommandHandler

from bot.context import Services
from bot.handlers.media import POLLS_KEY
from bot.handlers.reminders import job_name
from tests.conftest import ADMIN_ID
from tests.fake_telegram import (
    FakeTelegram,
    callback_update,
    inline_query_update,
    message_update,
    pre_checkout_update,
)


async def send(app: Application, text: str | None = None, **kwargs: object) -> None:
    await app.process_update(message_update(app.bot, text, **kwargs))  # type: ignore[arg-type]


async def press(app: Application, data: str, **kwargs: object) -> None:
    await app.process_update(callback_update(app.bot, data, **kwargs))  # type: ignore[arg-type]


# ----------------------------------------------------------------------------- startup


async def test_startup_publishes_localised_command_menus(settings, fake: FakeTelegram) -> None:
    from bot.app import build_application, on_shutdown, on_startup

    app = build_application(settings, request=fake)
    await app.initialize()
    await on_startup(app)
    try:
        calls = fake.find("setMyCommands")
        languages = {call.get("language_code") for call in calls}
        assert {None, "en", "ru"} <= languages
        admin_calls = [c for c in calls if c.get("scope", {}).get("chat_id") == ADMIN_ID]
        assert admin_calls, "admins get an extended command list"
        assert any(c["command"] == "stats" for c in admin_calls[0]["commands"])
        assert len(fake.find("setMyDescription")) == 2
    finally:
        await on_shutdown(app)
        await app.shutdown()


# ----------------------------------------------------------------------------- start


async def test_start_registers_user_and_shows_menus(
    app: Application, fake: FakeTelegram, services: Services
) -> None:
    await send(app, "/start", user_id=1)
    texts = fake.texts()
    assert "Hi, <b>Ann</b>" in texts[0]
    assert "Main menu" in texts[1]
    first = fake.find("sendMessage")[0]
    assert "keyboard" in first["reply_markup"], "a reply keyboard is attached"
    assert await services.users.get(1) is not None

    fake.reset()
    await send(app, "/start", user_id=1)
    assert "Welcome back" in fake.texts()[0]


async def test_start_in_russian_for_russian_client(app: Application, fake: FakeTelegram) -> None:
    await send(app, "/start", user_id=5, language_code="ru")
    assert "Привет" in fake.texts()[0]


async def test_referral_deep_link(app: Application, fake: FakeTelegram, services: Services) -> None:
    await send(app, "/start", user_id=1)
    await send(app, "/start ref_1", user_id=2)
    assert any("invite link" in text for text in fake.texts())
    assert await services.users.count_referrals(1) == 1

    # Existing users cannot be "referred" later.
    await send(app, "/start ref_2", user_id=1)
    assert await services.users.count_referrals(2) == 0


async def test_item_deep_link_opens_card(app: Application, fake: FakeTelegram) -> None:
    await send(app, "/start item_10")
    assert any("<b>Ruff</b>" in text for text in fake.texts())


async def test_help_hides_admin_commands_from_users(app: Application, fake: FakeTelegram) -> None:
    await send(app, "/help", user_id=1)
    assert "/stats" not in fake.texts()[-1]
    await send(app, "/help", user_id=ADMIN_ID)
    assert "/stats" in fake.texts()[-1]


async def test_reply_keyboard_button(app: Application, fake: FakeTelegram) -> None:
    await send(app, "❓ Помощь", language_code="ru")
    assert "/catalog" in fake.texts()[-1]


# ----------------------------------------------------------------------------- catalogue


async def test_catalog_pagination_edits_message(app: Application, fake: FakeTelegram) -> None:
    await send(app, "/catalog")
    assert "page 1 of 5" in fake.texts()[-1]

    fake.reset()
    await press(app, "catalog:page:4")
    edit = fake.find("editMessageText")[0]
    assert "page 5 of 5" in edit["text"]
    assert edit["message_id"] == 77
    assert fake.methods()[0] == "answerCallbackQuery"

    fake.reset()
    await press(app, "catalog:item:1:4")
    assert "python-telegram-bot" in fake.find("editMessageText")[0]["text"]


# ----------------------------------------------------------------------------- settings


async def test_language_switch_is_persisted(
    app: Application, fake: FakeTelegram, services: Services
) -> None:
    await send(app, "/settings")
    await press(app, "settings:lang:ru")
    record = await services.users.get(1)
    assert record is not None
    assert record.language == "ru"
    assert "Настройки сохранены" in fake.texts()[-1]

    fake.reset()
    await send(app, "/help")  # the Telegram client is English, but the choice wins
    assert "Что я умею" in fake.texts()[0]

    await press(app, "settings:lang:auto")
    fake.reset()
    await send(app, "/help")
    assert "What I can do" in fake.texts()[0]


# ----------------------------------------------------------------------------- feedback


async def test_feedback_conversation(
    app: Application, fake: FakeTelegram, services: Services
) -> None:
    await send(app, "/feedback")
    await send(app, "R2D2")  # invalid name
    assert "only contain letters" in fake.texts()[-1]
    await send(app, "Ann Lee")
    await send(app, "not-an-email")
    assert "valid e-mail" in fake.texts()[-1]
    await send(app, "/skip")
    await press(app, "feedback:rate:5")
    await send(app, "short")
    assert "too short" in fake.texts()[-1]
    await send(app, "A really helpful demo bot!")
    assert "Please check your feedback" in fake.texts()[-1]
    await press(app, "feedback:send")

    assert await services.feedback.count_and_average() == (1, 5.0)
    admin_messages = [p for p in fake.find("sendMessage") if p["chat_id"] == ADMIN_ID]
    assert admin_messages
    assert "Feedback #1" in admin_messages[0]["text"]

    # After the conversation ends, text goes to the regular handlers again.
    fake.reset()
    await send(app, "hello")
    assert "You wrote" in fake.texts()[-1]


async def test_feedback_cancel(app: Application, fake: FakeTelegram, services: Services) -> None:
    await send(app, "/feedback")
    await send(app, "Ann")
    await send(app, "/cancel")
    assert "Cancelled" in fake.texts()[-1]
    await send(app, "/cancel")
    assert "Nothing to cancel" in fake.texts()[-1]
    assert await services.feedback.count_and_average() == (0, None)


async def test_feedback_via_deep_link_and_cancel_button(
    app: Application, fake: FakeTelegram
) -> None:
    await send(app, "/start feedback")
    assert "What is your name" in fake.texts()[-1]
    await send(app, "✖️ Cancel")
    assert "Cancelled" in fake.texts()[-1]


# ----------------------------------------------------------------------------- reminders


async def test_remind_schedules_and_persists(
    app: Application, fake: FakeTelegram, services: Services
) -> None:
    await send(app, "/remind 1h 30m stretch")
    assert "in 1h 30m" in fake.texts()[-1]
    [reminder] = await services.reminders.pending(1)
    assert reminder.text == "stretch"
    assert app.job_queue is not None
    assert app.job_queue.get_jobs_by_name(job_name(reminder.id))

    await send(app, "/reminders")
    assert "stretch" in fake.texts()[-1]

    await press(app, f"reminder:del:{reminder.id}")
    assert await services.reminders.pending(1) == []
    await asyncio.sleep(0)
    assert not [j for j in app.job_queue.get_jobs_by_name(job_name(reminder.id)) if j.enabled]


@pytest.mark.parametrize(
    ("command", "expected"),
    [("/remind", "Usage"), ("/remind 10m", "What should I remind"), ("/remind 99d x", "30 days")],
)
async def test_remind_errors(
    app: Application, fake: FakeTelegram, command: str, expected: str
) -> None:
    await send(app, command)
    assert expected in fake.texts()[-1]


async def test_reminder_job_sends_message(
    app: Application, fake: FakeTelegram, services: Services
) -> None:
    from bot.handlers.reminders import fire_reminder
    from bot.storage.repositories import utcnow

    await services.users.upsert(1, "Ann", language_code="ru")
    reminder = await services.reminders.add(1, 1, "чай", utcnow())
    context = type("Ctx", (), {})()  # minimal stand-in for the job context
    context.job = type("Job", (), {"data": reminder.id})()
    context.services = services
    context.bot = app.bot
    await fire_reminder(context)  # type: ignore[arg-type]

    sent = fake.find("sendMessage")[-1]
    assert "Напоминание" in sent["text"]
    assert (
        sent["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
        == f"reminder:snooze:{reminder.id}"
    )
    assert await services.reminders.pending(1) == []


# ----------------------------------------------------------------------------- admin


async def test_admin_commands_are_hidden_from_users(app: Application, fake: FakeTelegram) -> None:
    await send(app, "/stats", user_id=1)
    assert "Unknown command" in fake.texts()[-1]


async def test_stats_for_admin(app: Application, fake: FakeTelegram) -> None:
    await send(app, "/start", user_id=1)
    await send(app, "/stats", user_id=ADMIN_ID)
    assert "Users: <b>2</b>" in fake.texts()[-1]


async def test_broadcast_with_confirmation(
    app: Application, fake: FakeTelegram, services: Services
) -> None:
    for user_id in (1, 2, 3):
        await services.users.upsert(user_id, f"U{user_id}")
    await send(app, "/broadcast <b>News</b>!", user_id=ADMIN_ID)
    assert "Send this to <b>4</b> users" in fake.texts()[-1]

    fake.reset()
    await press(app, "broadcast:send", user_id=ADMIN_ID)
    await asyncio.sleep(0.05)  # the handler runs with block=False
    recipients = {p["chat_id"] for p in fake.find("sendMessage")}
    assert recipients == {1, 2, 3, ADMIN_ID}
    assert "Delivered: 4" in fake.find("editMessageText")[-1]["text"]


async def test_broadcast_cancel(app: Application, fake: FakeTelegram) -> None:
    await send(app, "/broadcast hi", user_id=ADMIN_ID)
    fake.reset()
    await press(app, "broadcast:cancel", user_id=ADMIN_ID)
    await asyncio.sleep(0.05)
    assert "cancelled" in fake.find("editMessageText")[-1]["text"]
    assert fake.find("sendMessage") == []


# ----------------------------------------------------------------------------- anti-flood


async def test_anti_flood_blocks_and_warns_once(
    app: Application, fake: FakeTelegram, services: Services
) -> None:
    services.rate_limiter.limit = 3
    for _ in range(6):
        await send(app, "/help", user_id=7)
    texts = fake.texts()
    assert sum("Too fast" in text for text in texts) == 1
    assert sum("What I can do" in text for text in texts) == 3


async def test_admins_are_not_throttled(
    app: Application, fake: FakeTelegram, services: Services
) -> None:
    services.rate_limiter.limit = 1
    for _ in range(3):
        await send(app, "/help", user_id=ADMIN_ID)
    assert not any("Too fast" in text for text in fake.texts())


# ----------------------------------------------------------------------------- media


@pytest.mark.parametrize(
    ("data", "method"),
    [
        ("media:photo", "sendPhoto"),
        ("media:album", "sendMediaGroup"),
        ("media:document", "sendDocument"),
        ("media:location", "sendLocation"),
        ("media:venue", "sendVenue"),
        ("media:contact", "sendContact"),
        ("media:quiz", "sendPoll"),
        ("media:next", "editMessageMedia"),
        ("dice:DARTS", "sendDice"),
    ],
)
async def test_media_buttons(app: Application, fake: FakeTelegram, data: str, method: str) -> None:
    await send(app, "/start")
    await press(app, data)
    assert fake.find(method)


async def test_poll_answers_are_reported(app: Application, fake: FakeTelegram) -> None:
    await send(app, "/poll")
    assert fake.find("sendPoll")[0]["is_anonymous"] is False
    poll_id = next(iter(app.bot_data[POLLS_KEY]))
    update = Update.de_json(
        {
            "update_id": 9000,
            "poll_answer": {
                "poll_id": poll_id,
                "user": {"id": 1, "is_bot": False, "first_name": "Ann"},
                "option_ids": [1],
                "option_persistent_ids": ["1"],
            },
        },
        app.bot,
    )
    await app.process_update(update)
    assert "voted for: <b>aiogram</b>" in fake.texts()[-1]


async def test_incoming_location(app: Application, fake: FakeTelegram) -> None:
    await send(app, None, location={"latitude": 51.5074, "longitude": -0.1278})
    assert "341" in fake.texts()[-1]  # km from London to the Eiffel Tower


async def test_incoming_photo_is_echoed_by_file_id(app: Application, fake: FakeTelegram) -> None:
    photo = [
        {"file_id": "small", "file_unique_id": "s", "width": 90, "height": 60, "file_size": 1000},
        {
            "file_id": "big",
            "file_unique_id": "b",
            "width": 1280,
            "height": 853,
            "file_size": 204800,
        },
    ]
    await send(app, None, photo=photo)
    sent = fake.find("sendPhoto")[-1]
    assert sent["photo"] == "big"
    assert "1280×853, 200.0 KB" in sent["caption"]


# ----------------------------------------------------------------------------- inline mode


async def test_inline_query(app: Application, fake: FakeTelegram) -> None:
    await app.process_update(inline_query_update(app.bot, "sql"))
    [answer] = fake.find("answerInlineQuery")
    titles = [result["title"] for result in answer["results"]]
    assert "Bold" in titles
    assert any("SQLAlchemy" in title for title in titles)
    assert answer["button"]["start_parameter"] == "inline"
    assert len({result["id"] for result in answer["results"]}) == len(answer["results"])


# ----------------------------------------------------------------------------- payments


async def test_donation_invoice_and_checkout(app: Application, fake: FakeTelegram) -> None:
    await press(app, "donate:10")
    [invoice] = fake.find("sendInvoice")
    assert invoice["currency"] == "XTR"
    assert invoice["prices"] == [{"label": "Donation", "amount": 10}]

    await app.process_update(pre_checkout_update(app.bot, invoice["payload"], 10))
    assert fake.find("answerPreCheckoutQuery")[-1]["ok"] is True

    await app.process_update(pre_checkout_update(app.bot, invoice["payload"], 999))
    assert fake.find("answerPreCheckoutQuery")[-1]["ok"] is False


async def test_unknown_donation_amount_is_ignored(app: Application, fake: FakeTelegram) -> None:
    await press(app, "donate:1000000")
    assert fake.find("sendInvoice") == []


# ----------------------------------------------------------------------------- errors & misc


async def test_error_handler_apologises_and_notifies_admins(
    app: Application, fake: FakeTelegram
) -> None:
    async def boom(update: Update, context: object) -> None:
        raise RuntimeError("kaboom")

    app.add_handler(CommandHandler("boom", boom), group=-3)
    await send(app, "/boom")
    await asyncio.sleep(0.05)  # error handlers run as background tasks
    texts = fake.texts()
    assert any("Something went wrong" in text for text in texts)
    report = [p for p in fake.find("sendMessage") if p["chat_id"] == ADMIN_ID]
    assert report
    assert "kaboom" in report[0]["text"]


async def test_blocking_the_bot_is_tracked(app: Application, services: Services) -> None:
    await send(app, "/start", user_id=3)
    member = {"user": {"id": 123456, "is_bot": True, "first_name": "Demo"}}
    update = Update.de_json(
        {
            "update_id": 9100,
            "my_chat_member": {
                "chat": {"id": 3, "type": "private"},
                "from": {"id": 3, "is_bot": False, "first_name": "U"},
                "date": 0,
                "old_chat_member": {**member, "status": "member"},
                "new_chat_member": {**member, "status": "kicked", "until_date": 0},
            },
        },
        app.bot,
    )
    await app.process_update(update)
    record = await services.users.get(3)
    assert record is not None
    assert record.is_blocked


async def test_unknown_command(app: Application, fake: FakeTelegram) -> None:
    await send(app, "/nope")
    assert "Unknown command" in fake.texts()[-1]
