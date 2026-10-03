"""Sliding-window rate limiter used by the anti-flood middleware."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Callable, Hashable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    retry_after: float = 0.0
    #: True only for the first rejected hit of a burst, so the user is warned once.
    should_warn: bool = False


class SlidingWindowRateLimiter:
    """Allow at most ``limit`` hits per ``period`` seconds for each key."""

    SWEEP_EVERY = 1_000

    def __init__(
        self, limit: int, period: float, clock: Callable[[], float] = time.monotonic
    ) -> None:
        if limit < 1 or period <= 0:
            raise ValueError("limit must be >= 1 and period must be > 0")
        self.limit = limit
        self.period = period
        self._clock = clock
        self._hits: defaultdict[Hashable, deque[float]] = defaultdict(deque)
        self._warned: set[Hashable] = set()
        self._calls = 0

    def hit(self, key: Hashable) -> RateLimitDecision:
        now = self._clock()
        self._calls += 1
        if self._calls % self.SWEEP_EVERY == 0:
            self._sweep(now)

        hits = self._hits[key]
        while hits and hits[0] <= now - self.period:
            hits.popleft()

        if len(hits) < self.limit:
            hits.append(now)
            self._warned.discard(key)
            return RateLimitDecision(allowed=True)

        retry_after = max(0.0, hits[0] + self.period - now)
        should_warn = key not in self._warned
        self._warned.add(key)
        return RateLimitDecision(allowed=False, retry_after=retry_after, should_warn=should_warn)

    def reset(self, key: Hashable | None = None) -> None:
        if key is None:
            self._hits.clear()
            self._warned.clear()
        else:
            self._hits.pop(key, None)
            self._warned.discard(key)

    def _sweep(self, now: float) -> None:
        """Forget keys that have been idle for a whole window to keep memory bounded."""
        idle = [
            key for key, hits in self._hits.items() if not hits or hits[-1] <= now - self.period
        ]
        for key in idle:
            self.reset(key)

    def __len__(self) -> int:
        return len(self._hits)
