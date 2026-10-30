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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

from legalmind.db import models as M
from legalmind.db.lookup import must_exist
from legalmind.domain.enums import ReviewStatus
from legalmind.security import audit as A
from legalmind.security import permissions as P
from legalmind.security.authorization import require_review_visible
from legalmind.security.errors import Forbidden
from legalmind.security.resolver import has_permission
from legalmind.workflow.review_lifecycle import (
    all_required_decisions_complete,
    reopen_if_finished,
    require_writable,
    transition,
)


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
    review = must_exist(db.get(M.Review, finding.review_id), "reviews row",
                        finding.review_id)
    require_writable(db, review)          # AM-178: no escalation on a superseded version

    existing = _active_escalation(db, finding_id)
    if existing is not None:
        return existing

    escalation = M.Escalation(finding_id=finding_id, raised_by=actor_id,
                              reason=reason, created_at=datetime.now(UTC))
    # Two requests can both pass the check above. `uq_escalations_one_active`
    # (one ACTIVE escalation per Finding, decision 339) refuses the second insert;
    # it is caught under a savepoint so the request survives, and the row that
    # won is returned — 43.28's idempotence, now held by the database.
    savepoint = db.begin_nested()
    try:
        db.add(escalation)
        db.flush()
        savepoint.commit()
    except IntegrityError:
        savepoint.rollback()
        return must_exist(_active_escalation(db, finding_id),
                          "escalations row", finding_id)

    A.record(db, action=A.LEGAL_FINDING_ESCALATED, entity_type="finding",
             entity_id=finding_id, actor_id=actor_id, request_id=request_id,
             after={"escalation_id": str(escalation.id)})

    _refresh_status(db, finding)
    # AM-175: an escalation on a finished review reopens it; the point needs a decision
    # made after the escalation (evaluation.workflow.effective_decision)
    reopen_if_finished(db, review, cause="escalation", actor_id=actor_id,
                       request_id=request_id)
    return escalation


def withdraw_escalation(db: DBSession, *, actor_id: UUID, finding_id: UUID,
                        request_id: str | None = None) -> None:
    escalation = _active_escalation(db, finding_id)
    if escalation is None:
        return
    finding = must_exist(db.get(M.Finding, finding_id), "findings row", finding_id)
    review = must_exist(db.get(M.Review, finding.review_id), "reviews row",
                        finding.review_id)
    contract = must_exist(db.get(M.Contract, review.contract_id), "contracts row",
                          review.contract_id)
    # AM-237 r3 (QA-015): withdrawing takes a point back from Legal, so only the person
    # who raised it, the contract's owner or a Legal Decision Authority may — never
    # another reader who merely holds `legal.review` (a Developer does, AB-12 r12).
    if actor_id not in (escalation.raised_by, contract.owner_id) and not has_permission(
            db, actor_id, P.LEGAL_DECISION):
        raise Forbidden("only the person who raised this escalation, the contract's "
                        "owner or a Legal Decision Authority can withdraw it")
    require_writable(db, review)          # QA-083: a superseded version is history
    escalation.withdrawn_at = datetime.now(UTC)
    db.flush()
    A.record(db, action=A.LEGAL_ESCALATION_WITHDRAWN, entity_type="finding",
             entity_id=finding_id, actor_id=actor_id, request_id=request_id)
    _refresh_status(db, finding)
    # nothing outstanding any more: a review reopened for this escalation settles again
    if (review.status is ReviewStatus.LEGAL_REVIEW
            and all_required_decisions_complete(db, review)):
        transition(db, review, ReviewStatus.RESOLVED, actor_id=actor_id,
                   request_id=request_id)
    _undo_reopen_if_nothing_changed(db, review, escalation, actor_id, request_id)


def _undo_reopen_if_nothing_changed(db: DBSession, review: M.Review,
                                    escalation: M.Escalation, actor_id: UUID,
                                    request_id: str | None) -> None:
    """QA-084: an escalation withdrawn before any point was decided again changed
    nothing, so the decision on the contract it set aside counts again — Legal is not
    asked to record the same "Sign as is" twice. Only when this escalation is what
    reopened the review, and no decision has been recorded on it since."""
    if (review.status is not ReviewStatus.RESOLVED or review.reopened_at is None
            or review.reopened_at < escalation.created_at):
        return
    decided_since = db.execute(
        select(M.LegalDecision.id)
        .join(M.Evaluation, M.Evaluation.id == M.LegalDecision.evaluation_id)
        .join(M.Finding, M.Finding.id == M.Evaluation.finding_id)
        .where(M.Finding.review_id == review.id,
               M.LegalDecision.created_at >= escalation.created_at).limit(1)).first()
    if decided_since is not None:
        return
    review.reopened_at = None
    outcome = db.execute(
        select(M.ContractOutcomeRecord.outcome)
        .where(M.ContractOutcomeRecord.review_id == review.id)
        .order_by(M.ContractOutcomeRecord.version_number.desc()).limit(1)).scalar()
    if outcome is not None and outcome.value != "ON_HOLD":
        transition(db, review, ReviewStatus.CLOSED, actor_id=actor_id,
                   request_id=request_id)
    db.flush()


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
