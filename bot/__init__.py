"""Staery demo bot: a showcase of the Telegram Bot API with python-telegram-bot."""

import os

# Opt in to the python-telegram-bot v23 behaviour: durations are ``datetime.timedelta``.
os.environ.setdefault("PTB_TIMEDELTA", "1")

__version__ = "2.0.0"
