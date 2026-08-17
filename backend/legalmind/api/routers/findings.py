"""Findings and escalation — locked 49.3, 49.7, Steps 4 and 22.

Locked 49.3 maps escalation to ``review.view``, not to ``legal.decision``, and
locked Step 4 says why:

    An escalation means "This requires authorized review."
    It does not mean "I approve this deviation."

So an ordinary User escalates (ROLE-03) and nothing about the Finding is disposed
of. What changes is that every Evaluation under the Finding now requires a decision
(D-3.5 clause d, F-3).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select

from legalmind.api.deps import Guard, get_guard
from legalmind.api.envelope import data
from legalmind.api.schemas import EscalationCreate
from legalmind.api.serializers import serialize_evaluation, serialize_finding
from legalmind.db import models as M
from legalmind.security import permissions as P
from legalmind.workflow.escalation import (
    escalate_finding,
    is_escalated,
    withdraw_escalation,
)

router = APIRouter(tags=["findings"])


@router.get("/findings/{finding_id}")
def get_finding(finding_id: UUID, guard: Guard = Depends(get_guard)) -> dict:
    finding = guard.finding(finding_id, P.FINDING_VIEW)
    return data(serialize_finding(guard.db, finding,
                                  legal_position=guard.sees_legal_position))


@router.get("/findings/{finding_id}/evaluations")
def list_evaluations(finding_id: UUID, guard: Guard = Depends(get_guard)) -> dict:
    """The authoritative layer, unwrapped.

    Returned flat here without a 49.7 r1 problem: this response carries no
    Finding-level ``classification``, so there is no derived summary that could be
    mistaken for the authoritative result.
    """
    finding = guard.finding(finding_id, P.EVALUATION_VIEW)
    escalated = is_escalated(guard.db, finding.id)
    evaluations = guard.db.execute(
        select(M.Evaluation)
        .where(M.Evaluation.finding_id == finding.id)
        .order_by(M.Evaluation.scope_key, M.Evaluation.id)
    ).scalars().all()
    return data([
        serialize_evaluation(guard.db, ev,
                             legal_position=guard.sees_legal_position,
                             escalated=escalated)
        for ev in evaluations
    ])


@router.post("/findings/{finding_id}/escalate", status_code=201)
def escalate(finding_id: UUID, body: EscalationCreate,
             guard: Guard = Depends(get_guard)) -> dict:
    """Raise a Finding for authorized review.

    Idempotent: an already-escalated Finding returns its existing escalation
    rather than stacking a second one (43.28).
    """
    guard.finding(finding_id, P.REVIEW_VIEW)
    escalation = escalate_finding(guard.db, actor_id=guard.user_id,
                                  finding_id=finding_id, reason=body.reason,
                                  request_id=guard.request_id)
    finding = guard.db.get(M.Finding, finding_id)
    return data({
        "escalation": {
            "id": str(escalation.id),
            "finding_id": str(escalation.finding_id),
            "raised_by": str(escalation.raised_by),
            "reason": escalation.reason,
            "created_at": escalation.created_at.isoformat(),
        },
        # The derived Finding status, so the caller can see that authorized review
        # is now required — and can see that no disposition was recorded.
        "finding": serialize_finding(guard.db, finding,
                                     legal_position=guard.sees_legal_position),
    })


@router.delete("/findings/{finding_id}/escalate")
def withdraw(finding_id: UUID, guard: Guard = Depends(get_guard)) -> dict:
    """Withdraw an escalation — the same act reversed, so the same permission.

    Withdrawal is recorded (``withdrawn_at``), never deleted: the escalation
    happened and the audit trail is append-only (AUD-01).
    """
    guard.finding(finding_id, P.REVIEW_VIEW)
    withdraw_escalation(guard.db, actor_id=guard.user_id, finding_id=finding_id,
                        request_id=guard.request_id)
    finding = guard.db.get(M.Finding, finding_id)
    return data(serialize_finding(guard.db, finding,
                                  legal_position=guard.sees_legal_position))
