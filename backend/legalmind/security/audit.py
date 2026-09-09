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
#: Somebody read a Contract they do not own. Recorded because it is a disclosure
#: of one user's document to another: the access is authorized, and it is also
#: exactly the kind of access an auditor should be able to enumerate afterwards.
#: Ownership reads are NOT recorded — an owner reading their own contract is not
#: a disclosure and logging every such GET would bury the ones that matter.
#: One action per basis, so "which rule let them in" is a query, not a guess:
#:   department scope  — a Department Lead reading a deal in their department
#:                       (AB-12 r3; also how any break-glass read shows up)
#:   legal scope       — `REC-09` (owner ruling 2026-09-04), retained for the
#:                       future legal workflow
CONTRACT_READ_VIA_DEPARTMENT_SCOPE = "contract.read_via_department_scope"
CONTRACT_READ_VIA_LEGAL_SCOPE = "contract.read_via_legal_scope"
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
# Reporting — a rendered copy of legal analysis leaving the system (owner
# directive 2026-08-31; 49.10 already named export generation as a limited
# surface, so the act was always expected to be consequential).
REPORT_EXPORTED = "report.exported"
# Assist lane (AB-3/AB-4). AM-30 t5: every generation call is recorded with the
# model identity, prompt version and a payload HASH — never the payload. 53.1 keeps
# this in the audit trail proper, because an operational log is never a substitute
# for the record of what left the building.
ASSIST_GENERATION_CALLED = "assist.generation_called"
# Type suggestion (owner, 2026-08-31): the assist lane proposed a Step 6 code and
# what it proposed — the human confirmation that later records a type is a
# separate, ordinary contract update. Hash only, never the payload (AM-30 t5).
ASSIST_TYPE_SUGGESTION_CALLED = "assist.type_suggestion_called"
# Contract lifecycle beyond the locked ContractStatus axis — AB-12 (2026-09-05).
# Archive replaces AM-37's two-mode delete: nothing is destroyed any more, so
# there is one action and its mirror. Rows written under the withdrawn actions
# (`contract.soft_deleted`, `contract.hard_deleted`) stay in the trail as they
# are — AUD-01, append-only.
CONTRACT_ARCHIVED = "contract.archived"
CONTRACT_RESTORED = "contract.restored"
#: AM-55 (2026-09-09): a real, unconditional DELETE beside Archive — owner's
#: explicit choice, accepting that an analyzed contract's Findings and
#: Evaluations go with it (DB cascade). This row is what survives the row.
CONTRACT_DELETED = "contract.deleted"
# P-1 (2026-09-06): the owner DECLARES Draft / Active / Superseded (Step 2); trailed.
CONTRACT_STATUS_CHANGED = "contract.status_changed"
#: AM-50 (2026-09-09): the document type was recorded, and by whom — a human's
#: explicit choice, or the assist lane's confident suggestion applied at intake.
#: The `after` payload carries `source` so the trail says which.
CONTRACT_TYPE_DECLARED = "contract.type_declared"
# AB-13 r8 — a profile several people may edit is exactly what AUD-01 is for.
COUNTERPARTY_CREATED = "counterparty.created"
COUNTERPARTY_UPDATED = "counterparty.updated"
CONTRACT_COUNTERPARTY_LINKED = "contract.counterparty_linked"
# Phase 5 (2026-09-06): a version re-read in place with the current parser (Option C).
DOCUMENT_REPROCESSED = "document.reprocessed"
# Ownership transfer (AB-12 r5). before_state/after_state carry the previous and
# the new owner; the reason travels in after_state. The actor is the Lead.
CONTRACT_OWNERSHIP_TRANSFERRED = "contract.ownership_transferred"
# Administration
ADMIN_DEPARTMENT_CREATED = "admin.department_created"
ADMIN_DEPARTMENT_UPDATED = "admin.department_updated"
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
