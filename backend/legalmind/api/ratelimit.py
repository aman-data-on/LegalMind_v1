"""Rate limiting — locked S-5 and 49.10.

Locked 49.10 applies limiting to authentication, analysis submission and export
generation, and is explicit that **thresholds are deployment configuration, not
specification**. The defaults below are therefore starting values a deployment
overrides (Step 55); they are not a specified control level.

Exceeding a limit returns 429 with **no detail about the limit's shape** — which
is why nothing here emits ``Retry-After`` or a remaining-quota header.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from collections import deque
from dataclasses import dataclass
from typing import Any, Protocol

from legalmind.config import broker_url
from legalmind.observability.logs import log_event
from legalmind.security.errors import SecurityError


class RateLimited(SecurityError):
    status_code = 429
    code = "RATE_LIMITED"


@dataclass(frozen=True)
class Limit:
    max_requests: int
    window_seconds: int


def _limit(env: str, default_max: int, default_window: int) -> Limit:
    return Limit(
        max_requests=int(os.environ.get(f"{env}_MAX", default_max)),
        window_seconds=int(os.environ.get(f"{env}_WINDOW", default_window)),
    )


# Deployment configuration, surfaced here only so the call sites can name a limit.
LOGIN = _limit("LEGALMIND_RATELIMIT_LOGIN", 10, 300)
ANALYSIS = _limit("LEGALMIND_RATELIMIT_ANALYSIS", 30, 3600)
EXPORT = _limit("LEGALMIND_RATELIMIT_EXPORT", 20, 3600)
SUGGEST_TYPE = _limit("LEGALMIND_RATELIMIT_SUGGEST_TYPE", 30, 3600)
# Ask (2026-09-11). The generation seam is the one PAID egress path and was the only
# one with no budget at all: a loop in a client could spend without limit. Generous
# enough that a real conversation never meets it — a working session is tens of
# questions, not hundreds. A threshold is deployment configuration (49.10), not a
# specified control level.
ASK = _limit("LEGALMIND_RATELIMIT_ASK", 120, 3600)


class RateLimiter(Protocol):
    def check(self, key: str, limit: Limit) -> None: ...


class InProcessRateLimiter:
    """Sliding window held in memory.

    Correct for a single process only. A multi-worker deployment backs this with
    the shared Redis already in the locked stack (Step 39) via
    ``LEGALMIND_RATELIMIT_BACKEND=redis`` — see :class:`RedisRateLimiter` and
    :func:`limiter_from_env`.
    """

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}

    def check(self, key: str, limit: Limit) -> None:
        now = time.monotonic()
        window = self._hits.setdefault(key, deque())
        cutoff = now - limit.window_seconds
        while window and window[0] < cutoff:
            window.popleft()
        if len(window) >= limit.max_requests:
            raise RateLimited("rate limit exceeded")
        window.append(now)

    def reset(self) -> None:
        self._hits.clear()


class RedisRateLimiter:
    """The same sliding window, held in the shared Redis (Step 39) so every API
    process counts against ONE budget per key.

    One sorted set per key: member = a unique hit id, score = wall-clock time.
    Each check is one MULTI: drop hits older than the window, add this hit, count,
    refresh the TTL to the window. Over the limit → the hit is removed again and
    ``RateLimited`` raised, exactly as the in-process limiter never records a
    refused attempt. Two processes racing at the boundary can both be refused,
    never both admitted — the safe direction for a spend control.

    **Fails OPEN.** If Redis is unreachable the request is ALLOWED and
    ``ratelimit.redis_unavailable`` is logged at WARNING. The limiter bounds
    spend and abuse (S-5); it is not an authorization control, and taking every
    login, Ask and export down with the broker would be the larger outage. The
    key is never logged — it carries a user id or client address.
    """

    _PREFIX = "legalmind:ratelimit:"       # keeps clear of Celery's keys

    def __init__(self, url: str | None = None, *, client: Any = None) -> None:
        if client is None:
            import redis  # lazy: celery[redis] pulls it in
            client = redis.Redis.from_url(url or _redis_url())
        self._redis = client

    def check(self, key: str, limit: Limit) -> None:
        rkey, now, member = self._PREFIX + key, time.time(), uuid.uuid4().hex
        try:
            pipe = self._redis.pipeline(transaction=True)
            pipe.zremrangebyscore(rkey, 0, now - limit.window_seconds)
            pipe.zadd(rkey, {member: now})
            pipe.zcard(rkey)
            pipe.expire(rkey, limit.window_seconds)
            count = pipe.execute()[2]
            if count > limit.max_requests:
                self._redis.zrem(rkey, member)
                raise RateLimited("rate limit exceeded")
        except RateLimited:
            raise
        except Exception as exc:            # redis.RedisError and socket failures
            log_event("ratelimit.redis_unavailable", level=logging.WARNING,
                      error=type(exc).__name__)


def _redis_url() -> str:
    url = os.environ.get("LEGALMIND_RATELIMIT_REDIS_URL") or broker_url()
    if not url:
        raise RuntimeError("LEGALMIND_RATELIMIT_BACKEND=redis needs "
                           "LEGALMIND_RATELIMIT_REDIS_URL or LEGALMIND_BROKER_URL")
    return url


def limiter_from_env() -> RateLimiter:
    """``LEGALMIND_RATELIMIT_BACKEND=redis`` → the shared limiter; anything else
    → in-process, so a single-process deployment is unchanged."""
    if os.environ.get("LEGALMIND_RATELIMIT_BACKEND", "").lower() == "redis":
        return RedisRateLimiter()
    return InProcessRateLimiter()


class NullRateLimiter:
    """Used where a test asserts something other than the limiter."""

    def check(self, key: str, limit: Limit) -> None:
        return None
