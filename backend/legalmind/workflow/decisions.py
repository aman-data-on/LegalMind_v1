"""Legal Decision service — locked Step 31 (as amended by AM-2/AM-5/AM-6),
AB-1.1, AM-12, AM-15, Step 47 SEC-05, SEC-09.

Three locked properties are enforced here rather than trusted:

* **A decision resolves exactly ONE Evaluation** and never implicitly disposes
  of another under the same Finding (AB-1.1). The API has no Finding-level
  decision entry point, and neither does this service.
* **Supersession is append-only** (Step 31 r14). There is no update path: a
  change creates a new version, and prior rows are immutable — enforced by a
  database trigger, so no code path can revise history.
* **The current decision is the highest version** (Step 31 r20, N-1 Option C).
  Derived, never flagged, so it cannot drift.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

from legalmind.db import models as M
from legalmind.domain.enums import DecisionType
from legalmind.evaluation.workflow import (
    current_decision,
    derive_finding_status,
    evaluation_requires_decision,
)
from legalmind.security import audit as A
from legalmind.security import permissions as P
from legalmind.security.authorization import require_review_visible
from legalmind.security.errors import Forbidden
from legalmind.security.resolver import has_permission
from legalmind.workflow.errors import SecondPersonRequired, VersionConflict

# Locked Step 23 / 47.5 — APPROVE_CUSTOMIZATION needs the additional grant.
_EXTRA_PERMISSION = {
    DecisionType.APPROVE_CUSTOMIZATION: P.LEGAL_APPROVE_CUSTOMIZATION,
}


@dataclass(frozen=True)
class DecisionRecorded:
    decision: M.LegalDecision
    finding_status: str
    is_effective: bool


def record_decision(
    db: DBSession,
    *,
    actor_id: UUID,
    evaluation_id: UUID,
    decision_type: DecisionType,
    justification: str,
    expected_version: int | None = None,
    requires_second_person: bool = False,
    request_id: str | None = None,
) -> DecisionRecorded:
    """Record a Legal Decision against one scoped Evaluation.

    Authorization order follows locked 43.23: object scope first, then operation
    permission — so a caller who cannot see the object gets 404 regardless of
    their permissions and the response never reveals existence.
    """
    evaluation = db.get(M.Evaluation, evaluation_id)
    if evaluation is None:
        from legalmind.security.errors import NotVisible
        raise NotVisible("evaluation not found")

    finding = db.get(M.Finding, evaluation.finding_id)
    review = require_review_visible(db, actor_id, finding.review_id)

    # SEC-02/SEC-05 — legal.decision is only ever an EXPLICIT grant; no bypass
    # reaches it, so a Super Admin without it cannot decide by any route.
    if not has_permission(db, actor_id, P.LEGAL_DECISION):
        _audit_denied(db, actor_id, evaluation_id, request_id)
        raise Forbidden("missing permission: legal.decision")

    extra = _EXTRA_PERMISSION.get(decision_type)
    if extra and not has_permission(db, actor_id, extra):
        _audit_denied(db, actor_id, evaluation_id, request_id)
        raise Forbidden(f"missing permission: {extra}")

    if not (justification or "").strip():
        # Locked Step 31 r11. The database also enforces NOT NULL (AM-15); this
        # rejects whitespace-only text, which the column cannot.
        raise Forbidden("a justification is required for every Legal Decision")

    next_version = _next_version(db, evaluation_id)
    if expected_version is not None and expected_version + 1 != next_version:
        raise VersionConflict(
            f"expected to write version {expected_version + 1}, "
            f"but version {next_version} is next")

    decision = M.LegalDecision(
        finding_id=finding.id,
        evaluation_id=evaluation_id,
        decision_type=decision_type,
        justification=justification,
        decided_by=actor_id,
        version_number=next_version,
    )
    db.add(decision)
    try:
        db.flush()
    except IntegrityError as exc:
        # The UNIQUE(evaluation_id, version_number) constraint is the real
        # concurrency guarantee (AM-12); surface it as 409, not a 500.
        db.rollback()
        raise VersionConflict(
            "another decision was recorded concurrently for this Evaluation"
        ) from exc

    effective = decision_is_effective(
        db, evaluation_id, requires_second_person=requires_second_person)

    # SEC-09 — every decision is auditable (Step 31 r19). Append-only.
    A.record(db, action=A.LEGAL_DECISION_RECORDED,
             entity_type="evaluation", entity_id=evaluation_id, actor_id=actor_id,
             request_id=request_id,
             after={"decision_type": decision_type.value,
                    "version_number": next_version,
                    "is_effective": effective})

    status = derive_finding_status(db, finding)
    finding.status = status
    db.flush()

    return DecisionRecorded(decision=decision, finding_status=status.value,
                            is_effective=effective)


def _next_version(db: DBSession, evaluation_id: UUID) -> int:
    current = db.execute(
        select(func.max(M.LegalDecision.version_number))
        .where(M.LegalDecision.evaluation_id == evaluation_id)
    ).scalar()
    return (current or 0) + 1


def decision_history(db: DBSession, evaluation_id: UUID) -> list[M.LegalDecision]:
    """Full version chain, oldest first. Nothing is ever removed."""
    return list(db.execute(
        select(M.LegalDecision)
        .where(M.LegalDecision.evaluation_id == evaluation_id)
        .order_by(M.LegalDecision.version_number)
    ).scalars().all())


def decision_is_effective(db: DBSession, evaluation_id: UUID, *,
                          requires_second_person: bool) -> bool:
    """Whether the current decision disposes of the Evaluation.

    ``REQUEST_CLARIFICATION`` never disposes (locked Step 31 r10).

    **Second-person approval (locked Step 31 r15, F-2).** r15 permits a
    Requirement to "require independent second-person approval for consequential
    contract-specific decisions" but does not specify the mechanism. Implemented
    here as co-signature within the append-only version chain: the current
    decision and the one immediately preceding it must share a ``decision_type``
    and have DIFFERENT actors. This needs no schema change and keeps the
    append-only guarantee intact — an alternative ``co_signed_by`` column would
    amend locked 42.17.
    """
    chain = decision_history(db, evaluation_id)
    if not chain:
        return False
    current = chain[-1]
    if current.decision_type is DecisionType.REQUEST_CLARIFICATION:
        return False
    if not requires_second_person:
        return True
    if len(chain) < 2:
        return False
    previous = chain[-2]
    return (previous.decision_type is current.decision_type
            and previous.decided_by != current.decided_by)


def require_effective_decision(db: DBSession, evaluation_id: UUID, *,
                               requires_second_person: bool) -> None:
    if not decision_is_effective(
            db, evaluation_id, requires_second_person=requires_second_person):
        raise SecondPersonRequired(
            "an independent second approval by a different authorized user is "
            "required before this decision takes effect")


def _audit_denied(db: DBSession, actor_id: UUID, evaluation_id: UUID,
                  request_id: str | None) -> None:
    A.record(db, action=A.AUTHZ_PERMISSION_DENIED, entity_type="evaluation",
             entity_id=evaluation_id, actor_id=actor_id, request_id=request_id)
