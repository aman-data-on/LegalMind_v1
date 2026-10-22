"""Where a review stands — AM-179's review stage (owner, 2026-10-22).

ONE derivation, read by every surface in scope (the Summary, the Findings header, the
report): nothing here is stored, everything comes from persisted state — the Review's
status and `reopened_at`, each Finding's status (recomputed at every write that changes
it), the current Legal Decisions, the active assignment and the contract decision.

Counts are per POINT (the fold `fold_keys` defines, AM-179), so the numbers a reader sees
are the cards they see. `review_stage` is its own vocabulary: never one of the five axes,
never a value of their fields (REC-06, DECISION_STATE_MODEL).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from legalmind.db import models as M
from legalmind.domain.enums import (
    ContractOutcome,
    DecisionType,
    FindingStatus,
    ReviewStatus,
)
from legalmind.evaluation.user_status import ACCEPTABLE, fold_keys
from legalmind.evaluation.workflow import current_decision
from legalmind.workflow import contract_outcome as CO
from legalmind.workflow.review_lifecycle import is_superseded

_ANALYSING = {ReviewStatus.DRAFT, ReviewStatus.UPLOADED, ReviewStatus.PROCESSING}
_FAILED = {ReviewStatus.ANALYSIS_FAILED, ReviewStatus.CANCELLED}


def _point_state(statuses: set[FindingStatus], user_status: str) -> str:
    if FindingStatus.AWAITING_CLARIFICATION in statuses:
        return "clarification"
    if FindingStatus.DECISION_REQUIRED in statuses:
        return "to_decide"
    if FindingStatus.RESOLVED in statuses:
        return "decided"
    return "matches" if user_status == ACCEPTABLE else "no_action"


def review_progress(db: DBSession, review: M.Review, *,
                    legal_position: bool = True) -> dict[str, Any]:
    rows = fold_keys(db, [review.id], legal_position=legal_position)[review.id]
    findings = {f.id: f for f in db.execute(
        select(M.Finding).where(M.Finding.review_id == review.id)).scalars()}

    # one entry per point: its members, in the order the server lists them
    points: dict[Any, list] = {}
    status_of: dict[Any, str] = {}
    for finding_id, key, user_status in rows:
        point = key if key is not None else finding_id
        points.setdefault(point, []).append(finding_id)
        status_of.setdefault(point, user_status)

    counts = {"to_decide": 0, "clarification": 0, "decided": 0, "no_action": 0,
              "matches": 0}
    decided_by_type: dict[str, int] = {}
    for point, members in points.items():
        state = _point_state({findings[m].status for m in members}, status_of[point])
        counts[state] += 1
        if state == "decided":
            kind = _point_decision(db, members)
            if kind:
                decided_by_type[kind] = decided_by_type.get(kind, 0) + 1

    history = CO.history(db, review.id)
    current = history[-1] if history else None
    reopened = (review.reopened_at is not None and current is not None
                and review.reopened_at > current.created_at)
    outcome = None if (current is None or reopened) else current.outcome
    contract = db.get(M.Contract, review.contract_id)
    owner = db.get(M.User, contract.owner_id) if contract is not None else None
    assignee = db.execute(
        select(M.User).join(M.ReviewAssignment, M.ReviewAssignment.user_id == M.User.id)
        .where(M.ReviewAssignment.review_id == review.id,
               M.ReviewAssignment.revoked_at.is_(None))
        .order_by(M.ReviewAssignment.created_at)).scalars().first()
    required = counts["to_decide"] + counts["clarification"] + counts["decided"]
    newer = is_superseded(db, review)

    stage, next_who = _stage(review, counts, required, outcome, reopened, newer,
                             assignee is not None)
    person = {"owner": owner, "reviewer": assignee}.get(next_who or "")
    return {
        "stage": stage,
        "outcome": outcome.value if outcome else None,
        "superseded_by": newer,
        "reopened_at": review.reopened_at.isoformat() if review.reopened_at else None,
        "total": len(points), "required": required, **counts,
        "decided_by_type": decided_by_type,
        "next": {"who": next_who,
                 "name": (person.name or person.email) if person else None},
        "assignee": ({"name": assignee.name, "email": assignee.email}
                     if assignee else None),
    }


def _point_decision(db: DBSession, members: list) -> str | None:
    """The decision a decided point carries: its members share it when decided as one
    point (AM-179); otherwise the first member's current decision speaks for it."""
    for finding_id in members:
        for ev_id in db.execute(select(M.Evaluation.id).where(
                M.Evaluation.finding_id == finding_id)).scalars():
            decision = current_decision(db, ev_id)
            if decision is not None and \
                    decision.decision_type is not DecisionType.REQUEST_CLARIFICATION:
                return decision.decision_type.value
    return None


def _stage(review: M.Review, counts: dict, required: int,
           outcome: ContractOutcome | None, reopened: bool, newer: int | None,
           assigned: bool) -> tuple[str, str | None]:
    """The first match wins (the plan's precedence): (stage, who acts next)."""
    status = review.status
    if newer:
        return "SUPERSEDED", None
    if status in _ANALYSING:
        return "ANALYSING", None
    if status in _FAILED:
        return "ANALYSIS_FAILED", "owner"
    # the client's answer leads only once nothing else waits on the reviewer — a point
    # still to decide is the work in hand (the count line says what awaits the client)
    if counts["clarification"] and not counts["to_decide"]:
        return "WAITING_FOR_CLARIFICATION", "reviewer" if assigned else "legal"
    if status is ReviewStatus.LEGAL_REVIEW or counts["to_decide"]:
        if reopened:
            return "REOPENED", "reviewer" if assigned else "legal"
        return ("WITH_LEGAL", "reviewer") if assigned else ("NOT_SENT", "owner")
    if status is ReviewStatus.CLOSED and outcome is not None:
        return "COMPLETE", "owner"
    if required == 0 and outcome is None:
        return "NO_ISSUES", "owner"
    return "CONTRACT_DECISION_PENDING", "reviewer" if assigned else "legal"
