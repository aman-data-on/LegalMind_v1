"""The reviewer's decision on the whole contract — AM-174 (owner, 2026-10-22).

Recorded by a `legal.decision` holder once every required point is decided (the Review
is RESOLVED). Sign as is / Sign after our changes / Do not sign close the Review
(Step 30 r11: CLOSED is formal completion after resolution); On hold keeps it RESOLVED.
Append-only, like Legal Decisions: a change of mind is a new version.

The code SUGGESTS an outcome from the round's decisions and answers (AM-396) and
records the suggestion beside the choice. It never records an outcome itself (rule 13).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

from legalmind.db import models as M
from legalmind.domain.deal_stage import final_of
from legalmind.domain.enums import ContractOutcome, DecisionType, ReviewStatus
from legalmind.security import audit as A
from legalmind.security import permissions as P
from legalmind.security.errors import Forbidden
from legalmind.security.resolver import has_permission
from legalmind.workflow.errors import InvalidTransition, VersionConflict
from legalmind.workflow.review_lifecycle import (
    all_required_decisions_complete,
    only_client_questions_open,
    require_writable,
    transition,
)

_CHANGED = "the decision on this contract was changed meanwhile"


_CHANGES_BACK = {DecisionType.REJECT, DecisionType.REQUIRE_COMPANY_STANDARD,
                 DecisionType.APPROVE_CUSTOMIZATION}


def suggest(db: DBSession, review: M.Review) -> ContractOutcome:
    """AM-396: read the round — this Review's decisions, those of the client version our
    reply answers, and the answers to that version's changes. Anything sending wording
    back (a Reject — "this clause must change" — a required standard, our wording, or an
    answer other than accepting theirs) → Sign after our changes; else Sign as is. Do not
    sign stays a person's choice."""
    # AM-405 (AB-213 D1): "Ask the client" sends the question in our reply — wording goes
    # back, so the deal moves on (Sign after our changes); never On hold with no action
    return (ContractOutcome.SIGN_WITH_CHANGES if changes_go_back(db, review)
            else ContractOutcome.SIGN_AS_IS)


def _target(review: M.Review, version: M.DocumentVersion | None) -> UUID:
    replied = (version.doc_metadata or {}).get("reply_to") if version else None
    return UUID(replied) if replied else review.document_version_id


def _round_answers(db: DBSession, review: M.Review) -> set[str]:
    """The current answer of each change in the round (the version our reply answers)."""
    C = M.ComparisonChoice
    target = _target(review, db.get(M.DocumentVersion, review.document_version_id))
    return set(db.execute(select(C.choice).where(C.right_version_id == target)
                          .distinct(C.row_key)
                          .order_by(C.row_key, C.version_number.desc())).scalars())


def changes_go_back(db: DBSession, review: M.Review) -> bool:
    if current_types(db, review.id) & _CHANGES_BACK:
        return True
    version = db.get(M.DocumentVersion, review.document_version_id)
    target = _target(review, version)
    if target != review.document_version_id:
        theirs = db.execute(select(M.Review.id)
                            .where(M.Review.document_version_id == target)
                            .order_by(M.Review.created_at.desc()).limit(1)).scalar()
        if theirs is not None and current_types(db, theirs) & _CHANGES_BACK:
            return True
    return any(c != "theirs" for c in _round_answers(db, review))


def is_final_copy(db: DBSession, review: M.Review) -> bool:
    """The Review is of a final contract (`AM-318`): a package or a final copy."""
    version = db.get(M.DocumentVersion, review.document_version_id)
    return version is not None and bool(final_of(version.doc_metadata))


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


#: `decidable`: every point decided (`AM-178`) · only client questions open (`AM-411`)
COMPLETE, ASKED = "complete", "asked"


def decidable(db: DBSession, review: M.Review) -> str | None:
    """Whether the contract decision may be recorded NOW, read from the points at write
    time — the one check the write, the form (`ready`), the header and the To-do share.
    COMPLETE: `AM-178` r1 as locked. ASKED (`AM-411` r1, C-33 option a): the Review is
    still with Legal only because Legal asked the client — it stays LEGAL_REVIEW (never
    RESOLVED: not every point is decided) and takes any decision but Sign as is."""
    if review.status in {ReviewStatus.RESOLVED, ReviewStatus.CLOSED}:
        return COMPLETE if all_required_decisions_complete(db, review) else None
    if review.status is ReviewStatus.LEGAL_REVIEW \
            and only_client_questions_open(db, review):
        return ASKED
    return None


def due(db: DBSession, review: M.Review) -> bool:
    """The contract decision can be recorded and none is current (none yet, or the Review
    was reopened since the last one, `AM-175`)."""
    if decidable(db, review) is None:
        return False
    chain = history(db, review.id)
    return not chain or bool(review.reopened_at
                             and review.reopened_at > chain[-1].created_at)


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
    require_writable(db, review)                   # AM-178: archived / superseded → 409
    # AM-178: checked against the points themselves at write time, not the status alone
    # — a late clarification on a finished review must block the contract decision
    kind = decidable(db, review)
    if kind is None:
        raise InvalidTransition("every point must be decided before the contract is")
    if kind == ASKED and outcome is ContractOutcome.SIGN_AS_IS:
        # AM-411 r2: a question to the client is open — the contract is not agreed as is
        raise InvalidTransition("a question to the client is open — choose Sign after "
                                "our changes, Do not sign or On hold")
    if outcome is ContractOutcome.SIGN_WITH_CHANGES and is_final_copy(db, review):
        # AM-318: the final contract IS the agreed text — signed as is, or not at all
        raise InvalidTransition("a final contract is signed as it is, or not signed — "
                                "for more changes, upload the client's version")
    if review.status is ReviewStatus.CLOSED and outcome is ContractOutcome.ON_HOLD:
        raise InvalidTransition("a closed review cannot be put on hold")
    if (outcome is ContractOutcome.SIGN_AS_IS and not is_final_copy(db, review)
            and changes_go_back(db, review)):
        # AM-396: an integrity guard on the person's own answers, never a decision
        raise InvalidTransition("points in this round send changes back — choose Sign "
                                "after our changes, Do not sign or On hold")
    chain = history(db, review.id)
    next_version = len(chain) + 1
    if expected_version is not None and expected_version + 1 != next_version:
        raise VersionConflict(_CHANGED)
    row = M.ContractOutcomeRecord(
        review_id=review.id, outcome=outcome,
        suggested=suggest(db, review),
        justification=justification, decided_by=actor_id, version_number=next_version,
        created_at=datetime.now(UTC))     # ordered against `reopened_at` (AM-175)
    try:
        with db.begin_nested():                   # AM-177: a clash undoes only this row
            db.add(row)
            db.flush()
    except IntegrityError as exc:
        raise VersionConflict(_CHANGED) from exc
    A.record(db, action=A.CONTRACT_OUTCOME_RECORDED, entity_type="review",
             entity_id=review.id, actor_id=actor_id, request_id=request_id,
             before={"outcome": chain[-1].outcome.value} if chain else None,
             after={"outcome": outcome.value, "suggested": row.suggested.value,
                    "version_number": next_version, "justification": justification,
                    "contract_id": str(review.contract_id),
                    "document_version_id": str(review.document_version_id)})
    if review.status is ReviewStatus.RESOLVED and outcome is not ContractOutcome.ON_HOLD:
        transition(db, review, ReviewStatus.CLOSED, actor_id=actor_id,
                   request_id=request_id)
    return row
