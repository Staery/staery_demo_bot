import pytest

from bot.services.rate_limiter import SlidingWindowRateLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


def test_allows_up_to_limit_then_blocks(clock: FakeClock) -> None:
    limiter = SlidingWindowRateLimiter(limit=3, period=10, clock=clock)
    assert all(limiter.hit("u").allowed for _ in range(3))
    decision = limiter.hit("u")
    assert not decision.allowed
    assert decision.retry_after == pytest.approx(10)


def test_warns_only_once_per_burst(clock: FakeClock) -> None:
    limiter = SlidingWindowRateLimiter(limit=1, period=10, clock=clock)
    limiter.hit("u")
    assert limiter.hit("u").should_warn
    assert not limiter.hit("u").should_warn
    clock.now += 10
    assert limiter.hit("u").allowed
    assert limiter.hit("u").should_warn  # a new burst warns again


def test_window_slides(clock: FakeClock) -> None:
    limiter = SlidingWindowRateLimiter(limit=2, period=10, clock=clock)
    limiter.hit("u")
    clock.now += 6
    limiter.hit("u")
    assert not limiter.hit("u").allowed
    clock.now += 4  # the first hit leaves the window
    assert limiter.hit("u").allowed
    decision = limiter.hit("u")
    assert not decision.allowed
    assert decision.retry_after == pytest.approx(6)


def test_keys_are_independent(clock: FakeClock) -> None:
    limiter = SlidingWindowRateLimiter(limit=1, period=10, clock=clock)
    assert limiter.hit(1).allowed
    assert limiter.hit(2).allowed
    assert not limiter.hit(1).allowed


def test_reset(clock: FakeClock) -> None:
    limiter = SlidingWindowRateLimiter(limit=1, period=10, clock=clock)
    limiter.hit("a")
    limiter.hit("b")
    limiter.reset("a")
    assert limiter.hit("a").allowed
    limiter.reset()
    assert len(limiter) == 0


def test_idle_keys_are_swept(clock: FakeClock) -> None:
    limiter = SlidingWindowRateLimiter(limit=5, period=1, clock=clock)
    for user in range(limiter.SWEEP_EVERY - 1):
        limiter.hit(user)
    clock.now += 5
    limiter.hit("trigger-sweep")
    assert len(limiter) <= 1


@pytest.mark.parametrize(("limit", "period"), [(0, 1), (1, 0), (1, -1)])
def test_invalid_arguments(limit: int, period: float) -> None:
    with pytest.raises(ValueError, match="limit"):
        SlidingWindowRateLimiter(limit, period)
