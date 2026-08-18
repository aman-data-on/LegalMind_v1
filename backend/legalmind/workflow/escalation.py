"""Escalation — locked Steps 4, 22, 24 r5; F-3.

Locked Step 4 is explicit about what escalation is and is not:

    An escalation means "This requires authorized review."
    It does not mean "I approve this deviation."

Recorded at **Finding** level, preserving the locked user-facing vocabulary, and
marking every Evaluation under that Finding as requiring a decision (F-3). A
normal User may escalate; that is the whole point of locked ROLE-03 — they can
compare, view and escalate, but never decide.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from legalmind.db import models as M
from legalmind.db.lookup import must_exist
from legalmind.security import audit as A
from legalmind.security import permissions as P
from legalmind.security.authorization import require_review_visible
from legalmind.security.errors import Forbidden
from legalmind.security.resolver import has_permission


def escalate_finding(db: DBSession, *, actor_id: UUID, finding_id: UUID,
                     reason: str, request_id: str | None = None) -> M.Escalation:
    """Raise a Finding for authorized review."""
    finding = must_exist(db.get(M.Finding, finding_id),
                         "findings row", finding_id)
    require_review_visible(db, actor_id, finding.review_id)

    # A normal User may escalate (ROLE-03); review.view is the gate, deliberately
    # NOT legal.decision — escalation is not a disposition.
    if not has_permission(db, actor_id, P.REVIEW_VIEW):
        raise Forbidden("missing permission: review.view")
    if not (reason or "").strip():
        raise Forbidden("an escalation must state a reason")

    existing = _active_escalation(db, finding_id)
    if existing is not None:
        return existing

    escalation = M.Escalation(finding_id=finding_id, raised_by=actor_id,
                              reason=reason)
    db.add(escalation)
    db.flush()

    A.record(db, action=A.LEGAL_FINDING_ESCALATED, entity_type="finding",
             entity_id=finding_id, actor_id=actor_id, request_id=request_id,
             after={"escalation_id": str(escalation.id)})

    _refresh_status(db, finding)
    return escalation


def withdraw_escalation(db: DBSession, *, actor_id: UUID, finding_id: UUID,
                        request_id: str | None = None) -> None:
    escalation = _active_escalation(db, finding_id)
    if escalation is None:
        return
    escalation.withdrawn_at = datetime.now(UTC)
    db.flush()
    A.record(db, action=A.LEGAL_ESCALATION_WITHDRAWN, entity_type="finding",
             entity_id=finding_id, actor_id=actor_id, request_id=request_id)
    finding = must_exist(db.get(M.Finding, finding_id),
                         "findings row", finding_id)
    _refresh_status(db, finding)


def is_escalated(db: DBSession, finding_id: UUID) -> bool:
    return _active_escalation(db, finding_id) is not None


def _active_escalation(db: DBSession, finding_id: UUID) -> M.Escalation | None:
    return db.execute(
        select(M.Escalation).where(
            M.Escalation.finding_id == finding_id,
            M.Escalation.withdrawn_at.is_(None))
    ).scalars().first()


def _refresh_status(db: DBSession, finding: M.Finding) -> None:
    """Recompute the derived Finding status (Step 30 r16, J-4)."""
    from legalmind.evaluation.workflow import derive_finding_status

    finding.status = derive_finding_status(
        db, finding, escalated=is_escalated(db, finding.id))
    db.flush()
