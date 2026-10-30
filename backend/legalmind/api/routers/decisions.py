"""Legal Decisions — locked 49.7, Step 31, AB-1.1, AM-12, AM-15, 47.5.

Four locked properties are visible in the route table itself:

* **Decisions target an Evaluation, never a Finding.** There is no
  ``POST /findings/{id}/decisions``, because a decision resolves exactly one
  Evaluation and must never implicitly dispose of another under the same Finding
  (AB-1.1).
* **There is no update endpoint.** Supersession is a create (Step 31 r14).
* **There is no endpoint that resolves a Finding or a Review.** Resolution is
  derived, never asserted (D-3.6, Step 30 r7/r16).
* ``legal.approve_customization`` is required *in addition* to ``legal.decision``
  for ``APPROVE_CUSTOMIZATION`` (Step 23, 47.5).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select

from legalmind.api.deps import CommitBeforeResponse, Guard, get_guard
from legalmind.api.envelope import data
from legalmind.api.errors import BusinessRuleRejected
from legalmind.api.schemas import DecisionCreate, GroupDecisionCreate
from legalmind.api.serializers import serialize_decision, serialize_decision_chain
from legalmind.db import models as M
from legalmind.db.lookup import must_exist
from legalmind.domain.enums import DecisionType, ReviewStatus
from legalmind.evaluation.user_status import group_ids
from legalmind.evaluation.workflow import effective_decision
from legalmind.security import permissions as P
from legalmind.security.errors import NotVisible
from legalmind.workflow.decisions import decision_history, record_decision
from legalmind.workflow.escalation import is_escalated
from legalmind.workflow.review_lifecycle import (
    all_required_decisions_complete,
    transition,
)

router = APIRouter(tags=["decisions"], route_class=CommitBeforeResponse)


@router.post("/evaluations/{evaluation_id}/decisions", status_code=201)
def create_decision(evaluation_id: UUID, body: DecisionCreate,
                    guard: Guard = Depends(get_guard)) -> dict:
    """Record a Legal Decision against one scoped Evaluation.

    A version collision surfaces as **409** through
    ``UNIQUE(evaluation_id, version_number)`` — optimistic concurrency falls out of
    the constraint and there is no separate ETag mechanism (N-1 Option C).

    Note the double check on authority. The guard checks here so the denial is
    audited and committed before the request aborts; ``record_decision`` checks
    again, so the service stays safe when called from anywhere else. Neither check
    can be reached by a bypass: ``legal.decision`` is only ever an explicit grant
    (SEC-02, ROLE-05).
    """
    evaluation = guard.evaluation(evaluation_id, P.LEGAL_DECISION)
    if body.decision_type is DecisionType.APPROVE_CUSTOMIZATION:
        guard.additional_permission(P.LEGAL_APPROVE_CUSTOMIZATION,
                                    entity_type="evaluation",
                                    entity_id=evaluation_id)

    recorded = record_decision(
        guard.db,
        actor_id=guard.user_id,
        evaluation_id=evaluation_id,
        decision_type=body.decision_type,
        justification=body.justification,
        expected_version=body.expected_version,
        requires_second_person=body.requires_second_person,
        request_id=guard.request_id,
    )

    finding = must_exist(guard.db.get(M.Finding, evaluation.finding_id),
                         "findings row", evaluation.finding_id)
    review = must_exist(guard.db.get(M.Review, finding.review_id),
                        "reviews row", finding.review_id)
    _advance_if_resolved(guard, review)

    return data({
        "decision": serialize_decision(recorded.decision, db=guard.db),
        # Derived, so the caller learns the consequence without asserting it.
        "finding_status": recorded.finding_status,
        # Step 31 r10 / r15 — a REQUEST_CLARIFICATION never disposes, and a
        # decision awaiting its independent second approval is recorded but not
        # yet effective.
        "is_effective": recorded.is_effective,
        "review_status": review.status.value,
    })


@router.get("/evaluations/{evaluation_id}/decisions")
def list_decisions(evaluation_id: UUID,
                   guard: Guard = Depends(get_guard)) -> dict:
    """The full version chain, oldest first, highest marked current (49.7).

    Gated on ``finding.view``, not ``legal.decision``: reading what was decided is
    not the same authority as deciding.
    """
    guard.evaluation(evaluation_id, P.FINDING_VIEW)
    return data(serialize_decision_chain(
        decision_history(guard.db, evaluation_id)))


def _advance_if_resolved(guard: Guard, review: M.Review) -> None:
    """Locked Step 30 r7 / r16 — RESOLVED is derived from the Findings.

    Done here rather than exposed as an endpoint precisely because r3 forbids a
    caller setting Review status. If outstanding decisions remain, nothing happens
    and the Review stays in LEGAL_REVIEW.
    """
    if (review.status is ReviewStatus.LEGAL_REVIEW
            and all_required_decisions_complete(guard.db, review)):
        transition(guard.db, review, ReviewStatus.RESOLVED,
                   actor_id=guard.user_id, request_id=guard.request_id)


@router.post("/reviews/{review_id}/decisions", status_code=201)
def create_group_decision(review_id: UUID, body: GroupDecisionCreate,
                          guard: Guard = Depends(get_guard)) -> dict:
    """AM-179 (owner, 2026-10-22): one decision on a point the reader sees as one card.

    Every listed Evaluation must belong to this Review and to ONE point (`group_ids`);
    each already decided is skipped, every other one gets its own Legal Decision through
    `record_decision` — same checks, same guards, same audit (AB-1.1's one row per
    Evaluation, made explicit). All or nothing: any refusal aborts the whole request.
    """
    review = guard.review(review_id, P.LEGAL_DECISION)
    if body.decision_type is DecisionType.APPROVE_CUSTOMIZATION:     # audited denial,
        guard.additional_permission(P.LEGAL_APPROVE_CUSTOMIZATION,   # as the single route
                                    entity_type="review", entity_id=review_id)
    db = guard.db
    ids = list(dict.fromkeys(body.evaluation_ids))
    rows = db.execute(
        select(M.Evaluation).join(M.Finding, M.Finding.id == M.Evaluation.finding_id)
        .where(M.Evaluation.id.in_(ids), M.Finding.review_id == review.id)
    ).scalars().all()
    if len(rows) != len(ids):
        raise NotVisible("evaluation not found")          # SEC-07: the one 404
    groups = group_ids(db, [review.id], legal_position=guard.sees_legal_position)
    if len({groups.get(ev.finding_id) for ev in rows}) != 1:
        raise BusinessRuleRejected("one decision covers the items of one point only")
    if set(body.expected_versions) != set(ids):
        raise BusinessRuleRejected("name the expected version of every listed item")
    decided, skipped = [], []
    for ev in sorted(rows, key=lambda e: ids.index(e.id)):
        # QA-045: "already decided" by the rule that resolves the point — a decision
        # made before an active escalation no longer answers it, so it is decided again
        current = effective_decision(db, ev, is_escalated(db, ev.finding_id))
        if current is not None and current.decision_type is not \
                DecisionType.REQUEST_CLARIFICATION:
            skipped.append(str(ev.id))                    # O4: already decided
            continue
        recorded = record_decision(
            db, actor_id=guard.user_id, evaluation_id=ev.id,
            decision_type=body.decision_type, justification=body.justification,
            expected_version=body.expected_versions[ev.id], request_id=guard.request_id)
        decided.append(serialize_decision(recorded.decision, db=db))
    _advance_if_resolved(guard, review)
    return data({"decided": decided, "skipped": skipped,
                 "review_status": review.status.value})
