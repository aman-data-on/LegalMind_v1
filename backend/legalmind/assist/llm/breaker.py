"""The circuit breaker in front of every model call (`AM-204`, plan D10).

A model that keeps failing — a daily-quota 429, an outage — is not called again for a
while: the reader gets the honest outage floor at once instead of a full timeout per
request (Azure/AWS circuit-breaker pattern). BREAKER_FAILURES infrastructure failures in
a row, within BREAKER_WINDOW_S, open the circuit for BREAKER_OPEN_S; the next call after
that is a trial, and a failed trial opens it again at once. Only the provider's
failures count (`provider_failure`): a refusal, a 400 from our own payload, an empty
candidate, or a timeout on the few seconds a turn had left is one request's failure,
never an outage. One breaker per model, shared by every request of this process; each
model has its own, so failover moves on at once.

With ``LEGALMIND_BREAKER_BACKEND=redis`` (2026-10-30) an open pause or quota circuit is
also written to Redis with its own expiry, so every API process skips the provider and
shows the pause, and a restart does not forget it. Redis down: per process, as before.
"""
from __future__ import annotations

import logging
import os
import re
import threading
import time
from collections.abc import Callable

from legalmind.assist.llm.generation import GenerationUnavailable
from legalmind.observability.logs import log_event

BREAKER_FAILURES = 3
BREAKER_WINDOW_S = 120.0
BREAKER_OPEN_S = 60.0
#: A timeout counts only when the call had at least this long (code review 2026-10-26).
BREAKER_MIN_BUDGET_S = 20.0
_PROVIDER_HTTP = re.compile(r"HTTP (?:402|429|5\d\d)\b")
#: AM-222 (2026-10-27): a 402 (credit ran out) or 429 (quota) marks the model PAUSED;
#: one 402 opens the circuit for PAUSE_OPEN_S. A success ends the pause; so does time —
#: a 402 shows for PAUSE_OPEN_S after it was last seen, a 429 only while its circuit is
#: open — so the notice never outlives the evidence. The kind and its start feed the
#: reader's notice; an ERROR line once an hour, the admin's.
_PAUSING = {"402": "payment", "429": "quota"}
PAUSE_OPEN_S = 600.0
ALERT_EVERY_S = 3600.0

_guard = threading.Lock()
_failures: dict[str, list[float]] = {}
_open_until: dict[str, float] = {}
_paused: dict[str, tuple[str, float, float]] = {}   # model -> (kind, since, last seen)
_alerted: dict[str, float] = {}
_SHARED_KEY = "legalmind:paused:"     # keeps clear of Celery's and the limiter's keys
_client: list = []


def _shared():
    """The Redis client when the pause is shared, else None."""
    if os.environ.get("LEGALMIND_BREAKER_BACKEND", "").strip().lower() != "redis":
        return None
    if not _client:
        import redis  # lazy: celery[redis] pulls it in

        from legalmind.config import broker_url
        url = os.environ.get("LEGALMIND_RATELIMIT_REDIS_URL") or broker_url()
        _client.append(redis.Redis.from_url(url, socket_timeout=0.5,
                                            socket_connect_timeout=0.5))
    return _client[0]


def _redis(action: Callable, fallback=None):
    """One Redis call; fails open to ``fallback`` (the per-process breaker)."""
    client = _shared()
    if client is None:
        return fallback
    try:
        return action(client)
    except Exception as exc:            # redis.RedisError and socket failures
        log_event("assist.breaker.redis_unavailable", level=logging.WARNING,
                  error=type(exc).__name__)
        return fallback


def _shared_paused() -> dict[str, tuple[str, float]]:
    """Pauses another process (or this one before a restart) opened."""
    def read(client) -> dict[str, tuple[str, float]]:
        out = {}
        for key in client.scan_iter(_SHARED_KEY + "*"):
            kind, _, since = (client.get(key) or b"").decode().partition("|")
            if kind:
                out[key.decode()[len(_SHARED_KEY):]] = (kind, float(since or 0))
        return out
    return _redis(read, {})


def reset() -> None:
    with _guard:
        _failures.clear()
        _open_until.clear()
        _paused.clear()
        _alerted.clear()


def paused(clock: Callable[[], float] = time.monotonic) -> dict[str, tuple[str, float]]:
    """Every model paused now: its kind ("payment" or "quota") and since (epoch s)."""
    now = clock()
    with _guard:
        local = {m: (kind, since) for m, (kind, since, seen) in _paused.items()
                 if (now - seen < PAUSE_OPEN_S if kind == "payment"
                     else now < _open_until.get(m, 0.0))}
    return {**_shared_paused(), **local}


def provider_failure(exc: GenerationUnavailable, budget_s: float | None = None) -> bool:
    """Whether a failure is the provider's: billing, quota or a server error, the network,
    or a timeout on a call that had time — never our payload or an empty answer."""
    said = str(exc)
    if "HTTP" in said:
        return bool(_PROVIDER_HTTP.search(said))
    if "candidate" in said or "choice" in said:
        return False
    if "imeout" in said or "timed out" in said:
        return budget_s is None or budget_s >= BREAKER_MIN_BUDGET_S
    return True                                    # connection refused, reset, DNS …


def guarded[T](model: str, call: Callable[[], T],
               clock: Callable[[], float] = time.monotonic, *,
               budget_s: float | None = None) -> T:
    """``call()`` unless ``model``'s circuit is open — then GenerationUnavailable."""
    now = clock()
    with _guard:
        is_open = now < _open_until.get(model, 0.0)
    if is_open or model in _shared_paused():
        log_event("assist.provider_circuit_open", level=logging.WARNING, model=model)
        kind = paused(clock).get(model, ("",))[0]
        raise GenerationUnavailable(f"circuit open for {model}"
                                    + (f" (paused: {kind})" if kind else ""))
    try:
        result = call()
    except GenerationUnavailable as exc:
        if not provider_failure(exc, budget_s):
            raise
        with _guard:
            recent = [t for t in _failures.get(model, []) if now - t <= BREAKER_WINDOW_S]
            recent.append(now)
            # the first call after the cool-down is the trial: failing, it opens again
            trial = now - _open_until.get(model, -BREAKER_WINDOW_S) < BREAKER_WINDOW_S
            if len(recent) >= BREAKER_FAILURES or trial:
                _open_until[model], recent = now + BREAKER_OPEN_S, []
            _failures[model] = recent
            status = re.search(r"HTTP (402|429)\b", str(exc))
            alert, shared = False, None
            if not status:              # another cause now: no pause to report
                _paused.pop(model, None)
            else:
                kind = _PAUSING[status.group(1)]
                same = _paused.get(model, ("",))[0] == kind
                since = _paused[model][1] if same else time.time()
                _paused[model] = (kind, since, now)
                if kind == "payment":   # a per-minute 429 must not stop Ask for 10 min
                    _open_until[model] = now + PAUSE_OPEN_S
                if now < _open_until.get(model, 0.0):   # only an OPEN circuit is shared
                    shared = (kind, since, _open_until[model] - now)
                alert = time.time() - _alerted.get(model, 0.0) >= ALERT_EVERY_S
                if alert:
                    _alerted[model] = time.time()
        if shared:
            kind, since, ttl = shared
            _redis(lambda c: c.set(_SHARED_KEY + model, f"{kind}|{since}",
                                   ex=max(1, int(ttl))))
        if alert:
            log_event("assist.provider_paused", level=logging.ERROR, model=model,
                      kind=kind, operational_failure=True)
        raise
    with _guard:
        _failures.pop(model, None)
        _open_until.pop(model, None)
        _paused.pop(model, None)
    return result
