"""Denial semantics — Step 47 §47.7 / SEC-07.

The distinction between Forbidden and NotVisible is legally significant. For a
contract, review or finding, confirming that an object with a given id EXISTS
is itself a disclosure — a counterparty name or an ongoing negotiation can be
inferred from existence alone (LEGAL-02, 41.24).
"""

from __future__ import annotations


class SecurityError(Exception):
    status_code: int = 500
    code: str = "SECURITY_ERROR"


class Unauthenticated(SecurityError):
    """401 — no valid session."""

    status_code = 401
    code = "UNAUTHENTICATED"


class Forbidden(SecurityError):
    """403 — the object is visible to this user, but the operation is not."""

    status_code = 403
    code = "FORBIDDEN"


class NotVisible(SecurityError):
    """404 — outside the caller's ownership/visibility scope.

    MUST be indistinguishable from "does not exist". The API layer renders both
    as a byte-identical 404 (49.5 r1); any difference is an enumeration oracle.
    """

    status_code = 404
    code = "NOT_FOUND"
