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
"""
from __future__ import annotations

import logging
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
#: one 402 opens the circuit for PAUSE_OPEN_S. The first success ends the pause. The
#: kind and its start feed the reader's notice; an ERROR line once an hour, the admin's.
_PAUSING = {"402": "payment", "429": "quota"}
PAUSE_OPEN_S = 600.0
ALERT_EVERY_S = 3600.0

_guard = threading.Lock()
_failures: dict[str, list[float]] = {}
_open_until: dict[str, float] = {}
_paused: dict[str, tuple[str, float]] = {}      # model -> (kind, epoch seconds since)
_alerted: dict[str, float] = {}


def reset() -> None:
    with _guard:
        _failures.clear()
        _open_until.clear()
        _paused.clear()
        _alerted.clear()


def paused() -> dict[str, tuple[str, float]]:
    """Every paused model: its kind ("payment" or "quota") and since when."""
    with _guard:
        return dict(_paused)


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
    if is_open:
        log_event("assist.provider_circuit_open", level=logging.WARNING, model=model)
        kind = paused().get(model, ("",))[0]
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
            alert = False
            if status:
                kind = _PAUSING[status.group(1)]
                _paused.setdefault(model, (kind, time.time()))
                if kind == "payment":   # a per-minute 429 must not stop Ask for 10 min
                    _open_until[model] = now + PAUSE_OPEN_S
                alert = time.time() - _alerted.get(model, 0.0) >= ALERT_EVERY_S
                if alert:
                    _alerted[model] = time.time()
        if alert:
            log_event("assist.provider_paused", level=logging.ERROR, model=model,
                      kind=kind, operational_failure=True)
        raise
    with _guard:
        _failures.pop(model, None)
        _open_until.pop(model, None)
        _paused.pop(model, None)
    return result
