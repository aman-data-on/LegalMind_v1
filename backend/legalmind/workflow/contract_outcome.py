"""The reviewer's decision on the whole contract — AM-174 (owner, 2026-10-22).

Recorded by a `legal.decision` holder once every required point is decided (the Review
is RESOLVED). Sign as is / Sign after our changes / Do not sign close the Review
(Step 30 r11: CLOSED is formal completion after resolution); On hold keeps it RESOLVED.
Append-only, like Legal Decisions: a change of mind is a new version.

The code SUGGESTS an outcome from the point decisions and records the suggestion beside
the choice. It never records an outcome itself (rule 13).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

from legalmind.db import models as M
from legalmind.domain.enums import ContractOutcome, DecisionType, ReviewStatus
from legalmind.security import audit as A
from legalmind.security import permissions as P
from legalmind.security.errors import Forbidden
from legalmind.security.resolver import has_permission
from legalmind.workflow.errors import InvalidTransition, VersionConflict
from legalmind.workflow.review_lifecycle import transition

_CHANGED = "the decision on this contract was changed meanwhile"


def suggest(decision_types: set[DecisionType]) -> ContractOutcome:
    """Any Reject → Do not sign; any wording to send back → Sign after our changes."""
    if DecisionType.REJECT in decision_types:
        return ContractOutcome.DO_NOT_SIGN
    if DecisionType.REQUIRE_COMPANY_STANDARD in decision_types:
        return ContractOutcome.SIGN_WITH_CHANGES
    return ContractOutcome.SIGN_AS_IS


def current_types(db: DBSession, review_id: UUID) -> set[DecisionType]:
    """Each Evaluation's current decision type (highest version wins)."""
    latest = (select(M.LegalDecision.evaluation_id,
                     func.max(M.LegalDecision.version_number).label("v"))
              .join(M.Finding, M.Finding.id == M.LegalDecision.finding_id)
              .where(M.Finding.review_id == review_id)
              .group_by(M.LegalDecision.evaluation_id).subquery())
    return set(db.execute(
        select(M.LegalDecision.decision_type)
        .join(latest, (latest.c.evaluation_id == M.LegalDecision.evaluation_id)
              & (latest.c.v == M.LegalDecision.version_number))).scalars())


def history(db: DBSession, review_id: UUID) -> list[M.ContractOutcomeRecord]:
    return list(db.execute(
        select(M.ContractOutcomeRecord)
        .where(M.ContractOutcomeRecord.review_id == review_id)
        .order_by(M.ContractOutcomeRecord.version_number)).scalars())


def record(db: DBSession, review: M.Review, *, actor_id: UUID,
           outcome: ContractOutcome, justification: str,
           expected_version: int | None = None,
           request_id: str | None = None) -> M.ContractOutcomeRecord:
    if not has_permission(db, actor_id, P.LEGAL_DECISION):     # SEC-01/SEC-02
        raise Forbidden("missing permission: legal.decision")
    if not justification.strip():
        raise Forbidden("a reason is required for the decision on the contract")
    if review.status not in {ReviewStatus.RESOLVED, ReviewStatus.CLOSED}:
        raise InvalidTransition("every point must be decided before the contract is")
    if review.status is ReviewStatus.CLOSED and outcome is ContractOutcome.ON_HOLD:
        raise InvalidTransition("a closed review cannot be put on hold")
    chain = history(db, review.id)
    next_version = len(chain) + 1
    if expected_version is not None and expected_version + 1 != next_version:
        raise VersionConflict(_CHANGED)
    row = M.ContractOutcomeRecord(
        review_id=review.id, outcome=outcome,
        suggested=suggest(current_types(db, review.id)),
        justification=justification, decided_by=actor_id, version_number=next_version)
    db.add(row)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise VersionConflict(_CHANGED) from exc
    A.record(db, action=A.CONTRACT_OUTCOME_RECORDED, entity_type="review",
             entity_id=review.id, actor_id=actor_id, request_id=request_id,
             before={"outcome": chain[-1].outcome.value} if chain else None,
             after={"outcome": outcome.value, "suggested": row.suggested.value,
                    "version_number": next_version, "justification": justification,
                    "contract_id": str(review.contract_id)})
    if review.status is ReviewStatus.RESOLVED and outcome is not ContractOutcome.ON_HOLD:
        transition(db, review, ReviewStatus.CLOSED, actor_id=actor_id,
                   request_id=request_id)
    return row
