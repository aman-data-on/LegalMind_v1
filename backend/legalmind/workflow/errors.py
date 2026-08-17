"""Workflow errors mapped to the locked API denial semantics (49.5)."""

from __future__ import annotations

from legalmind.security.errors import SecurityError


class VersionConflict(SecurityError):
    """409 — a decision version collision (locked 49.7, AM-12).

    Raised when two writers both claim the same ``version_number``. The database
    UNIQUE constraint is the real guarantee; this surfaces it as a meaningful
    outcome rather than an internal error, which is what gives optimistic
    concurrency without a separate ETag mechanism.
    """

    status_code = 409
    code = "DECISION_VERSION_CONFLICT"


class InvalidTransition(SecurityError):
    """422 — a Review lifecycle transition the locked state machine forbids."""

    status_code = 422
    code = "INVALID_TRANSITION"


class SecondPersonRequired(SecurityError):
    """422 — the configured independent second approval is not yet present."""

    status_code = 422
    code = "SECOND_PERSON_APPROVAL_REQUIRED"
