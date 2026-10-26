"""The circuit breaker in front of every model call (`AM-204`, plan D10).

A model that keeps failing — a daily-quota 429, an outage — is not called again for a
while: the reader gets the honest outage floor at once instead of a full timeout per
request (Azure/AWS circuit-breaker pattern). BREAKER_FAILURES infrastructure failures in
a row, within BREAKER_WINDOW_S, open the circuit for BREAKER_OPEN_S; the next call after
that is a trial. A refusal (`GenerationRefused`) is the payload's fault, not the
provider's, and never counts. One breaker per model, shared by every request of this
process; each model has its own, so failover moves on at once.
"""
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

from legalmind.assist.llm.generation import GenerationUnavailable
from legalmind.observability.logs import log_event

BREAKER_FAILURES = 3
BREAKER_WINDOW_S = 120.0
BREAKER_OPEN_S = 60.0

_guard = threading.Lock()
_failures: dict[str, list[float]] = {}
_open_until: dict[str, float] = {}


def reset() -> None:
    with _guard:
        _failures.clear()
        _open_until.clear()


def guarded[T](model: str, call: Callable[[], T],
               clock: Callable[[], float] = time.monotonic) -> T:
    """``call()`` unless ``model``'s circuit is open — then GenerationUnavailable."""
    now = clock()
    with _guard:
        is_open = now < _open_until.get(model, 0.0)
    if is_open:
        log_event("assist.provider_circuit_open", level=logging.WARNING, model=model)
        raise GenerationUnavailable(f"circuit open for {model}")
    try:
        result = call()
    except GenerationUnavailable:
        with _guard:
            recent = [t for t in _failures.get(model, []) if now - t <= BREAKER_WINDOW_S]
            recent.append(now)
            if len(recent) >= BREAKER_FAILURES:
                _open_until[model], recent = now + BREAKER_OPEN_S, []
            _failures[model] = recent
        raise
    with _guard:
        _failures.pop(model, None)
    return result
