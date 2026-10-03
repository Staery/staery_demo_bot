"""Questions for the quiz poll demo."""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class QuizQuestion:
    question: dict[str, str]
    options: dict[str, tuple[str, ...]]
    correct: int
    explanation: dict[str, str]


QUESTIONS: tuple[QuizQuestion, ...] = (
    QuizQuestion(
        question={
            "en": "What is the maximum size of inline button callback data?",
            "ru": "Каков максимальный размер callback data у inline-кнопки?",
        },
        options={
            "en": ("32 bytes", "64 bytes", "256 bytes", "4096 bytes"),
            "ru": ("32 байта", "64 байта", "256 байт", "4096 байт"),
        },
        correct=1,
        explanation={
            "en": "callback_data is limited to 1–64 bytes.",
            "ru": "callback_data ограничена 1–64 байтами.",
        },
    ),
    QuizQuestion(
        question={
            "en": "Which update delivery method needs a public HTTPS URL?",
            "ru": "Какой способ получения апдейтов требует публичный HTTPS-адрес?",
        },
        options={
            "en": ("Long polling", "Webhook", "Both", "Neither"),
            "ru": ("Long polling", "Webhook", "Оба", "Ни один"),
        },
        correct=1,
        explanation={
            "en": "Telegram pushes updates to your webhook URL over HTTPS.",
            "ru": "Telegram отправляет апдейты на ваш webhook по HTTPS.",
        },
    ),
    QuizQuestion(
        question={
            "en": "What is the currency code of Telegram Stars?",
            "ru": "Какой код валюты у Telegram Stars?",
        },
        options={
            "en": ("TGS", "STR", "XTR", "TON"),
            "ru": ("TGS", "STR", "XTR", "TON"),
        },
        correct=2,
        explanation={
            "en": "Digital goods are paid in Stars, currency code XTR.",
            "ru": "Цифровые товары оплачиваются в Stars, код валюты XTR.",
        },
    ),
)


def random_question(rng: random.Random | None = None) -> QuizQuestion:
    return (rng or random).choice(QUESTIONS)
