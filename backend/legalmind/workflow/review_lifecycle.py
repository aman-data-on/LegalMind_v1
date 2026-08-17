"""Review lifecycle — locked Step 30.

    DRAFT -> UPLOADED -> PROCESSING -> ANALYSIS_COMPLETE
          -> LEGAL_REVIEW (when required) -> RESOLVED -> CLOSED

    Exceptions:  PROCESSING -> ANALYSIS_FAILED
                 DRAFT / UPLOADED -> CANCELLED

Locked rules enforced here:
  r2   the lifecycle is a controlled state machine
  r3   users cannot arbitrarily set Review status
  r6   LEGAL_REVIEW is entered only when the workflow requires Legal intervention
  r7   RESOLVED means all required workflow/Legal decisions are complete
  r8   RESOLVED != MATCH  (and r9, r10)
  r11  CLOSED represents formal completion AFTER resolution
  r13  ANALYSIS_FAILED is distinct from a Finding of UNABLE_TO_EVALUATE
  r16  final summaries are DERIVED, not stored in an editable field
  r17  each transition generates an Audit Trail event
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from legalmind.db import models as M
from legalmind.domain.enums import FindingStatus, ReviewStatus
from legalmind.evaluation.workflow import derive_finding_status
from legalmind.security import audit as A
from legalmind.workflow.errors import InvalidTransition

# Locked Step 30 state machine. Anything absent here is forbidden (r2).
ALLOWED_TRANSITIONS: dict[ReviewStatus, frozenset[ReviewStatus]] = {
    ReviewStatus.DRAFT: frozenset({ReviewStatus.UPLOADED, ReviewStatus.CANCELLED}),
    ReviewStatus.UPLOADED: frozenset({ReviewStatus.PROCESSING,
                                      ReviewStatus.CANCELLED}),
    ReviewStatus.PROCESSING: frozenset({ReviewStatus.ANALYSIS_COMPLETE,
                                        ReviewStatus.ANALYSIS_FAILED}),
    ReviewStatus.ANALYSIS_COMPLETE: frozenset({ReviewStatus.LEGAL_REVIEW,
                                               ReviewStatus.RESOLVED}),
    ReviewStatus.LEGAL_REVIEW: frozenset({ReviewStatus.RESOLVED}),
    ReviewStatus.RESOLVED: frozenset({ReviewStatus.CLOSED}),
    ReviewStatus.CLOSED: frozenset(),
    ReviewStatus.ANALYSIS_FAILED: frozenset(),
    ReviewStatus.CANCELLED: frozenset(),
}


def transition(db: DBSession, review: M.Review, target: ReviewStatus, *,
               actor_id: UUID | None = None,
               request_id: str | None = None) -> M.Review:
    """Apply a controlled lifecycle transition.

    Callers name a target; they never assign ``review.status`` directly (r3).
    """
    current = review.status
    if target not in ALLOWED_TRANSITIONS[current]:
        raise InvalidTransition(
            f"{current.value} -> {target.value} is not a permitted Review "
            "lifecycle transition")

    if target is ReviewStatus.RESOLVED and not all_required_decisions_complete(db, review):
        # r7 — RESOLVED means all required decisions are complete. Refusing here
        # is what keeps RESOLVED from becoming a manually assertable summary.
        raise InvalidTransition(
            "cannot resolve: one or more Findings still require a Legal Decision")

    review.status = target
    if target is ReviewStatus.PROCESSING and review.started_at is None:
        review.started_at = datetime.now(timezone.utc)
    if target in {ReviewStatus.RESOLVED, ReviewStatus.CLOSED,
                  ReviewStatus.ANALYSIS_FAILED, ReviewStatus.CANCELLED}:
        review.completed_at = datetime.now(timezone.utc)
    db.flush()

    # r17 — every transition is audited.
    A.record(db, action=A.REVIEW_STATUS_CHANGED, entity_type="review",
             entity_id=review.id, actor_id=actor_id, request_id=request_id,
             before={"status": current.value}, after={"status": target.value})
    return review


def requires_legal_review(db: DBSession, review: M.Review) -> bool:
    """r6 — LEGAL_REVIEW is entered only when a Finding requires a decision."""
    return any(
        derive_finding_status(db, f, escalated=_escalated(db, f.id))
        in {FindingStatus.DECISION_REQUIRED, FindingStatus.AWAITING_CLARIFICATION}
        for f in _findings(db, review)
    )


def all_required_decisions_complete(db: DBSession, review: M.Review) -> bool:
    """r7 / Step 31 r18 — derived from Findings, never stored (r16)."""
    findings = _findings(db, review)
    if not findings:
        return True
    for finding in findings:
        status = derive_finding_status(db, finding,
                                      escalated=_escalated(db, finding.id))
        if status in {FindingStatus.DECISION_REQUIRED,
                      FindingStatus.AWAITING_CLARIFICATION}:
            return False
    return True


def advance_after_analysis(db: DBSession, review: M.Review, *,
                           actor_id: UUID | None = None,
                           request_id: str | None = None) -> ReviewStatus:
    """Move a PROCESSING Review forward once analysis has produced Findings.

    Chooses LEGAL_REVIEW or RESOLVED from the derived Finding states (r6, r16) —
    the caller does not decide.
    """
    if review.status is ReviewStatus.PROCESSING:
        transition(db, review, ReviewStatus.ANALYSIS_COMPLETE,
                   actor_id=actor_id, request_id=request_id)
    if requires_legal_review(db, review):
        transition(db, review, ReviewStatus.LEGAL_REVIEW,
                   actor_id=actor_id, request_id=request_id)
    else:
        transition(db, review, ReviewStatus.RESOLVED,
                   actor_id=actor_id, request_id=request_id)
    return review.status


def _findings(db: DBSession, review: M.Review) -> list[M.Finding]:
    return list(db.execute(
        select(M.Finding).where(M.Finding.review_id == review.id)
    ).scalars().all())


def _escalated(db: DBSession, finding_id: UUID) -> bool:
    from legalmind.workflow.escalation import is_escalated
    return is_escalated(db, finding_id)
