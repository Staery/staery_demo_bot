"""Small formatting and geo helpers."""

from __future__ import annotations

import math
from datetime import timedelta

EARTH_RADIUS_KM = 6371.0088


def human_size(num_bytes: int | None) -> str:
    """``1536`` -> ``"1.5 KB"``."""
    if num_bytes is None:
        return "?"
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{int(size)} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    raise AssertionError("unreachable")  # pragma: no cover


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points in kilometres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def to_seconds(value: int | float | timedelta | None) -> int:
    """Durations are ints in older Bot API wrappers and ``timedelta`` in newer ones."""
    if value is None:
        return 0
    if isinstance(value, timedelta):
        return int(value.total_seconds())
    return int(value)
