"""Observability — locked Step 53.

Locked 53.1 keeps three record types apart and they must never be conflated:

    audit events    what legally happened      append-only (AUD-01)
    diagnostics     why the engine concluded   immutable with the Evaluation (REC-07)
    operational logs what the system did       retention-bound

This package owns only the third. It is deliberately the least powerful of the
three: locked 53.1 states that "nothing in the log pipeline is authoritative for any
legal conclusion", and that "losing logs must never lose legal history".

So nothing here writes to `audit_events`, nothing here can alter an Evaluation, and
no code path depends on a log line having been emitted.
"""

from legalmind.observability.logs import (
    configure_logging,
    log_event,
    log_exception,
)
from legalmind.observability.metrics import (
    ANALYSIS_SIGNALS,
    classification_signal,
    is_operational_failure,
)
from legalmind.observability.redaction import redact_fields

__all__ = [
    "ANALYSIS_SIGNALS",
    "classification_signal",
    "configure_logging",
    "is_operational_failure",
    "log_event",
    "log_exception",
    "redact_fields",
]
