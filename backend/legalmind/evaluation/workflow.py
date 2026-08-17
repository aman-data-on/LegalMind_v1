"""Decision-requirement and Finding resolution — locked D-3.5, D-3.6, J-4.

These are workflow rules, deliberately separate from the evaluators: the engine
produces no decision, no status and no resolution (36.15, 45A r18, 45B.14).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from legalmind.db import models as M
from legalmind.domain.enums import (
    DecisionType,
    FindingClassification,
    FindingStatus,
    RuleOutcome,
)
from legalmind.evaluation.rollup import is_tier_1

# D-3.5(a)
DECISION_REQUIRING_OUTCOMES = frozenset({
    RuleOutcome.APPROVAL_REQUIRED,
    RuleOutcome.UNACCEPTABLE,
})


def evaluation_requires_decision(
    *,
    classification: FindingClassification,
    rule_outcome: RuleOutcome,
    requirement_required: bool,
    escalated: bool = False,
) -> bool:
    """Locked D-3.5. An Evaluation requires a Legal Decision if ANY of:

        (a) rule_outcome in {APPROVAL_REQUIRED, UNACCEPTABLE}
        (b) classification is Tier 1 (cannot be relied upon)
        (c) classification is MISSING and the Requirement is required
        (d) it has been escalated by a user (Step 4, Step 22)

    Configuration may only WIDEN this set, never narrow it (F-4): it reconciles
    Step 27 r12 (severity is configuration-driven) with ENG-09 (fail-closed).
    """
    if rule_outcome in DECISION_REQUIRING_OUTCOMES:
        return True
    if is_tier_1(classification):
        return True
    if classification is FindingClassification.MISSING and requirement_required:
        return True
    return bool(escalated)


def widen_decision_requirement(baseline: bool, configured: bool) -> bool:
    """F-4 — configuration may add a requirement, never remove one."""
    return baseline or configured


def current_decision(db: DBSession, evaluation_id: UUID) -> M.LegalDecision | None:
    """The current decision is the HIGHEST version_number (N-1 Option C).

    Prior versions are never updated or deleted, so "current" is derived rather
    than flagged — which is what makes locked Step 31 r14 and r20 implementable
    without mutating history.
    """
    return db.execute(
        select(M.LegalDecision)
        .where(M.LegalDecision.evaluation_id == evaluation_id)
        .order_by(M.LegalDecision.version_number.desc())
        .limit(1)
    ).scalars().first()


def finding_is_resolved(db: DBSession, finding: M.Finding, *,
                        requirement_required: bool = True,
                        escalated: bool = False) -> bool:
    """Locked D-3.6.

        Finding is RESOLVED  <=>  for every Evaluation E:
            E does not require a decision
            OR E has a current Legal Decision whose type != REQUEST_CLARIFICATION

    MATCH / ACCEPTABLE Evaluations requiring no decision are satisfied trivially
    and never block resolution.
    """
    evaluations = db.execute(
        select(M.Evaluation).where(M.Evaluation.finding_id == finding.id)
    ).scalars().all()
    if not evaluations:
        # EV-MIN makes this a defect rather than a resolvable state.
        return False

    for ev in evaluations:
        if not evaluation_requires_decision(
            classification=ev.classification,
            rule_outcome=ev.rule_outcome,
            requirement_required=requirement_required,
            escalated=escalated,
        ):
            continue
        decision = current_decision(db, ev.id)
        if decision is None:
            return False
        if decision.decision_type is DecisionType.REQUEST_CLARIFICATION:
            # Step 31 r10 — leaves the workflow unresolved until completed.
            return False
    return True


def derive_finding_status(db: DBSession, finding: M.Finding, *,
                         requirement_required: bool = True,
                         escalated: bool = False) -> FindingStatus:
    """Locked J-4 / D-4.1.

    Status is derived, never asserted by a caller (Step 30 r16: summaries are
    derived rather than stored in a manually editable field).
    """
    evaluations = db.execute(
        select(M.Evaluation).where(M.Evaluation.finding_id == finding.id)
    ).scalars().all()

    outstanding_clarification = False
    needs_decision = False
    for ev in evaluations:
        if not evaluation_requires_decision(
            classification=ev.classification,
            rule_outcome=ev.rule_outcome,
            requirement_required=requirement_required,
            escalated=escalated,
        ):
            continue
        decision = current_decision(db, ev.id)
        if decision is None:
            needs_decision = True
        elif decision.decision_type is DecisionType.REQUEST_CLARIFICATION:
            outstanding_clarification = True

    if outstanding_clarification:
        return FindingStatus.AWAITING_CLARIFICATION
    if needs_decision:
        return FindingStatus.DECISION_REQUIRED
    if any(evaluation_requires_decision(
            classification=ev.classification, rule_outcome=ev.rule_outcome,
            requirement_required=requirement_required, escalated=escalated)
           for ev in evaluations):
        return FindingStatus.RESOLVED
    # Nothing ever required a decision. OPEN is terminal-but-actionable:
    # escalation can still move it to DECISION_REQUIRED (D-4.1).
    return FindingStatus.OPEN
