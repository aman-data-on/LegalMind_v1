"""Operational logging — locked 53.1, 53.2, 53.3, 53.4.

Structured JSON lines, correlated by ``X-Request-Id`` (49.9 / 53.2), with locked
53.3's prohibitions enforced by construction rather than by convention.

--------------------------------------------------------------------------
Two audiences, deliberately separated (53.4)
--------------------------------------------------------------------------
    user-facing      stable code, safe message, request_id   -> API response
    operator-facing  stack trace, context, correlation id     -> log pipeline only

"An operator-facing detail must never leak into an API response. The `request_id` is
the bridge." So `log_exception` records the traceback here and returns nothing the
API could accidentally serialize; the API's own handler already emits only the locked
envelope.

--------------------------------------------------------------------------
Why there is no `extra=`-style escape hatch
--------------------------------------------------------------------------
Every field goes through `redact_fields`. There is deliberately no way to log a raw
string payload: `log_event` takes an event name plus keyword fields, so a caller
cannot smuggle contract text through an f-string. That closes the gap 53.3 would
otherwise leave to caller discipline.

No log line is load-bearing. Locked 53.1: "Losing logs must never lose legal
history", and "nothing in the log pipeline is authoritative for any legal
conclusion". Nothing in this module writes to `audit_events` or touches an
Evaluation.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from contextlib import contextmanager
from typing import Any, Iterator

from legalmind.observability.redaction import redact_fields

LOGGER_NAME = "legalmind"
_logger = logging.getLogger(LOGGER_NAME)


class JsonFormatter(logging.Formatter):
    """One JSON object per line.

    Structured because 53.2 makes `request_id` a join key: correlating a request to
    its audit events and the Evaluations it produced has to be a query, not a grep.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "event": record.getMessage(),
        }
        fields = getattr(record, "legalmind_fields", None)
        if fields:
            payload.update(fields)
        if record.exc_info:
            # Operator-facing only (53.4). The API response carries a stable code
            # and a safe message; this is the other side of that bridge.
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, sort_keys=True)


def configure_logging(level: str | None = None) -> None:
    """Idempotent: safe to call from the app factory and from a worker entry point.

    Log destination, aggregation technology and retention are deployment choices —
    locked 53.6 records log aggregation as NOT YET SPECIFIED — so this writes to
    stdout and lets the platform collect it.
    """
    resolved = (level or os.environ.get("LEGALMIND_LOG_LEVEL", "INFO")).upper()
    _logger.setLevel(resolved)
    _logger.propagate = False
    for existing in list(_logger.handlers):
        _logger.removeHandler(existing)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    _logger.addHandler(handler)


def log_event(event: str, *, level: int = logging.INFO,
              request_id: str | None = None, **fields: Any) -> None:
    """Emit one operational log line.

    ``event`` is a stable identifier, never an interpolated sentence — an event name
    is searchable and cannot smuggle content. Every field is redacted per 53.3.
    """
    safe = redact_fields(fields)
    if request_id:
        safe["request_id"] = request_id          # 53.2 — the join key
    _logger.log(level, event, extra={"legalmind_fields": safe})


def log_exception(event: str, *, request_id: str | None = None,
                  **fields: Any) -> None:
    """Record an operator-facing failure with its traceback (53.4).

    Called from an active `except` block. The caller is expected to have already
    produced a safe user-facing response; nothing is returned here that could be
    serialized into one.
    """
    safe = redact_fields(fields)
    if request_id:
        safe["request_id"] = request_id
    _logger.log(logging.ERROR, event, exc_info=True,
                extra={"legalmind_fields": safe})


@contextmanager
def timed(event: str, *, request_id: str | None = None,
          **fields: Any) -> Iterator[dict[str, Any]]:
    """Time a pipeline stage — locked 53.5's "analysis pipeline stage durations".

    Yields a dict the caller may add fields to, so a stage can report what it
    produced (counts, versions — never content) alongside its duration.
    """
    extra: dict[str, Any] = {}
    started = time.monotonic()
    try:
        yield extra
    finally:
        log_event(event, request_id=request_id,
                  duration_ms=round((time.monotonic() - started) * 1000, 2),
                  **fields, **extra)
