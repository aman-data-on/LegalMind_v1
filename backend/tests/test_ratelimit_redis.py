"""RedisRateLimiter — S-5, design review §5.1.

One budget per key across processes; window expiry frees it; Redis down fails
OPEN with a warning. ``fakeredis`` is not installed, so a minimal fake covers
exactly the five commands the limiter issues.
"""

from __future__ import annotations

import logging

import pytest

from legalmind.api import ratelimit
from legalmind.api.ratelimit import Limit, RateLimited, RedisRateLimiter

LIMIT = Limit(max_requests=3, window_seconds=10)


class FakeRedis:
    """Sorted sets only: zremrangebyscore / zadd / zcard / expire / zrem."""

    def __init__(self) -> None:
        self.sets: dict[str, dict[str, float]] = {}
        self.ttl: dict[str, int] = {}

    def pipeline(self, transaction: bool = True) -> FakeRedis:
        self._queued: list = []
        return self

    def zremrangebyscore(self, k: str, lo: float, hi: float) -> None:
        z = self.sets.setdefault(k, {})
        self._queued.append(len([m for m, s in list(z.items())
                                 if lo <= s <= hi and z.pop(m) is not None]))

    def zadd(self, k: str, mapping: dict[str, float]) -> None:
        self.sets.setdefault(k, {}).update(mapping)
        self._queued.append(len(mapping))

    def zcard(self, k: str) -> None:
        self._queued.append(len(self.sets.get(k, {})))

    def expire(self, k: str, seconds: int) -> None:
        self.ttl[k] = seconds
        self._queued.append(True)

    def execute(self) -> list:
        out, self._queued = self._queued, []
        return out

    def zrem(self, k: str, member: str) -> int:
        return int(self.sets.get(k, {}).pop(member, None) is not None)


class DownRedis:
    def pipeline(self, transaction: bool = True) -> DownRedis:
        raise ConnectionError("redis unreachable")


def test_allows_up_to_the_limit_then_refuses_and_frees_on_expiry(monkeypatch):
    clock = [1_000.0]
    monkeypatch.setattr(ratelimit.time, "time", lambda: clock[0])
    fake = FakeRedis()
    limiter = RedisRateLimiter(client=fake)
    for _ in range(LIMIT.max_requests):
        limiter.check("ask:u1", LIMIT)
    with pytest.raises(RateLimited):
        limiter.check("ask:u1", LIMIT)
    # The refused attempt was not recorded, and the key carries the window's TTL.
    assert len(fake.sets["legalmind:ratelimit:ask:u1"]) == LIMIT.max_requests
    assert fake.ttl["legalmind:ratelimit:ask:u1"] == LIMIT.window_seconds
    clock[0] += LIMIT.window_seconds + 1
    limiter.check("ask:u1", LIMIT)                     # window expired: allowed


def test_two_instances_share_one_budget():
    """The whole point of §5.1: two API processes against one Redis count as one."""
    fake = FakeRedis()
    a, b = RedisRateLimiter(client=fake), RedisRateLimiter(client=fake)
    a.check("ask:u1", LIMIT)
    b.check("ask:u1", LIMIT)
    a.check("ask:u1", LIMIT)
    with pytest.raises(RateLimited):
        b.check("ask:u1", LIMIT)
    b.check("ask:u2", LIMIT)                           # a different key is separate


def test_redis_down_fails_open_with_a_warning(caplog):
    limiter = RedisRateLimiter(client=DownRedis())
    with caplog.at_level(logging.WARNING, logger="legalmind"):
        limiter.check("ask:u1", LIMIT)                 # allowed, not raised
    record = next(r for r in caplog.records if r.getMessage() == "ratelimit.redis_unavailable")
    assert record.legalmind_fields["error"] == "ConnectionError"
    assert "u1" not in str(record.legalmind_fields)    # the key is never logged


def test_factory_defaults_to_in_process_and_selects_redis_by_env(monkeypatch):
    monkeypatch.delenv("LEGALMIND_RATELIMIT_BACKEND", raising=False)
    assert isinstance(ratelimit.limiter_from_env(), ratelimit.InProcessRateLimiter)
    monkeypatch.setenv("LEGALMIND_RATELIMIT_BACKEND", "redis")
    monkeypatch.setenv("LEGALMIND_BROKER_URL", "redis://127.0.0.1:1/0")
    assert isinstance(ratelimit.limiter_from_env(), RedisRateLimiter)
    monkeypatch.delenv("LEGALMIND_BROKER_URL")
    with pytest.raises(RuntimeError):                  # no URL anywhere: loud, not silent
        ratelimit.limiter_from_env()
