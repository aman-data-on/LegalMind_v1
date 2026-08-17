"""Rate limiting — locked S-5 and 49.10.

Locked 49.10 applies limiting to authentication, analysis submission and export
generation, and is explicit that **thresholds are deployment configuration, not
specification**. The defaults below are therefore starting values a deployment
overrides (Step 55); they are not a specified control level.

Exceeding a limit returns 429 with **no detail about the limit's shape** — which
is why nothing here emits ``Retry-After`` or a remaining-quota header.
"""

from __future__ import annotations

import os
import time
from collections import deque
from dataclasses import dataclass
from typing import Protocol

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


class RateLimiter(Protocol):
    def check(self, key: str, limit: Limit) -> None: ...


class InProcessRateLimiter:
    """Sliding window held in memory.

    Correct for a single process only. A multi-worker deployment must back this
    with the shared Redis already in the locked stack (Step 39) — the limiter is
    an injected dependency precisely so that swap is a deployment concern and not
    a code change.
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


class NullRateLimiter:
    """Used where a test asserts something other than the limiter."""

    def check(self, key: str, limit: Limit) -> None:
        return None
