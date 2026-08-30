"""Authentication and authorization events — Step 47 §47.9 / SEC-09.

Recorded in the existing locked ``audit_events`` table (42.18). No new audit
table: 42.18 is entity-shaped and accommodates these directly, and ``actor_id``
is nullable so pre-authentication events can be recorded.

Never recorded here: credentials, credential hashes, session identifiers, OIDC
tokens or authorization codes (S-4); contract text; internal legal position
(LEGAL-02). Log records carry identifiers, not content.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session as DBSession

from legalmind.db import models as M

# Authentication
AUTH_LOGIN_SUCCEEDED = "auth.login_succeeded"
AUTH_LOGIN_FAILED = "auth.login_failed"
AUTH_LOGOUT = "auth.logout"
AUTH_SESSION_REVOKED = "auth.session_revoked"
# Authorization
AUTHZ_PERMISSION_DENIED = "authz.permission_denied"
AUTHZ_OBJECT_NOT_VISIBLE = "authz.object_not_visible"
# Analysis
ANALYSIS_RUN_RECORDED = "analysis.run_recorded"
ANALYSIS_RUN_FAILED = "analysis.run_failed"
# Legal workflow
LEGAL_DECISION_RECORDED = "legal.decision_recorded"
LEGAL_FINDING_ESCALATED = "legal.finding_escalated"
LEGAL_ESCALATION_WITHDRAWN = "legal.escalation_withdrawn"
REVIEW_STATUS_CHANGED = "review.status_changed"
# Legal configuration — closing the gap where every other privileged router
# recorded audit events and configuration writes did not. A change to a
# Company Standard is at least as consequential as a role grant.
CONFIG_REQUIREMENT_CREATED = "config.requirement_created"
CONFIG_VERSION_CREATED = "config.version_created"
CONFIG_STANDARD_UPDATED = "config.standard_updated"
CONFIG_PUBLISHED = "config.published"
# Assist lane (AB-3/AB-4). AM-30 t5: every generation call is recorded with the
# model identity, prompt version and a payload HASH — never the payload. 53.1 keeps
# this in the audit trail proper, because an operational log is never a substitute
# for the record of what left the building.
ASSIST_GENERATION_CALLED = "assist.generation_called"
# Administration
ADMIN_ROLE_GRANTED = "admin.role_granted"
ADMIN_ROLE_REVOKED = "admin.role_revoked"
ADMIN_LEGAL_AUTHORITY_GRANTED = "admin.legal_authority_granted"
ADMIN_LEGAL_AUTHORITY_REVOKED = "admin.legal_authority_revoked"
ADMIN_PERMISSION_CHANGED = "admin.permission_changed"


def record(db: DBSession, *, action: str, entity_type: str,
           entity_id: UUID | None = None, actor_id: UUID | None = None,
           request_id: str | None = None,
           before: dict[str, Any] | None = None,
           after: dict[str, Any] | None = None) -> M.AuditEvent:
    """Append an audit event.

    Append-only is enforced by a database trigger (AUD-01), so this is the only
    way a row ever enters the table and no path can later rewrite it.
    """
    meta: dict[str, Any] = {}
    if request_id:
        meta["request_id"] = request_id      # correlation (49.9)
    event = M.AuditEvent(
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before_state=before,
        after_state=after,
        event_metadata=meta or None,
    )
    db.add(event)
    db.flush()
    return event
