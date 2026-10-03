"""Logging configuration."""

import logging

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(format=LOG_FORMAT, level=level)
    # httpx logs every request to the Bot API at INFO level, which is too noisy.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
