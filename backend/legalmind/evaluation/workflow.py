"""Decision-requirement and Finding resolution — locked D-3.5, D-3.6, J-4.

These are workflow rules, deliberately separate from the evaluators: the engine
produces no decision, no status and no resolution (36.15, 45A r18, 45B.14).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from legalmind.db import models as M
from legalmind.db.lookup import contract_principals
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

#: **The owner's V1 fail-closed policy, 2026-08-18.**
#:
#: *"If there is no explicit Legal Rule in the supplied material telling LegalMind
#: whether that deviation is acceptable, requires approval, or is unacceptable, the
#: outcome should remain NOT_APPLICABLE and be sent for human Legal review."*
#:
#: This is a **widening** of the locked D-3.5 baseline, which F-4 expressly permits
#: ("Configuration may only WIDEN this set, never narrow it") and which ENG-09
#: favours: it sends strictly more to a human, never less. Nothing is narrowed and
#: no locked decision is amended.
#:
#: It is needed because D-3.5 alone does not cover this case. `DEVIATION` is Tier 2,
#: so without this a deviation carrying `NOT_APPLICABLE` matched none of D-3.5's
#: four conditions and the Finding derived to `OPEN` — meaning "nothing ever
#: required a decision". Locked Step 20 r4 says the opposite in prose: with no rule
#: "the deviation stands and a human decides". This closes that gap.
#:
#: `DEVIATION` + `NOT_APPLICABLE` is exactly the un-ruled case, and always is:
#: `_rule_outcome_for` returns `NOT_APPLICABLE` only when no Legal Rule is
#: configured or no configured threshold applies to the value. So the condition
#: never fires where a rule has actually dispositioned the deviation.
#:
#: Consequence, recorded rather than discovered later: **no Legal Rule exists
#: anywhere in V1**, so in practice every deviation now requires a Legal Decision,
#: and a Review holding one cannot complete until an authorized human rules on it.
#: That is the requested behaviour, not a side effect.
#:
#: Set `False` only alongside an approved Legal Rule that dispositions deviations.
UNRULED_DEVIATION_REQUIRES_DECISION = True


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

    (e) is that widening, per the owner's V1 policy — see
    ``UNRULED_DEVIATION_REQUIRES_DECISION``.
    """
    if rule_outcome in DECISION_REQUIRING_OUTCOMES:
        return True
    if is_tier_1(classification):
        return True
    if classification is FindingClassification.MISSING and requirement_required:
        return True
    # (e) A deviation no configured rule has dispositioned. Widening only.
    if widen_decision_requirement(
        baseline=False,
        configured=(UNRULED_DEVIATION_REQUIRES_DECISION
                    and classification is FindingClassification.DEVIATION
                    and rule_outcome is RuleOutcome.NOT_APPLICABLE),
    ):
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


def effective_decision(db: DBSession, ev: M.Evaluation,
                        escalated: bool) -> M.LegalDecision | None:
    """The current decision, if it still answers the point (AM-175, 2026-10-22).

    An escalation asks for the point to be looked at again: a decision recorded BEFORE
    the active escalation no longer answers it, so the escalated point needs a new one
    (amends D-3.6's "has a current Legal Decision" for escalated points only)."""
    decision = current_decision(db, ev.id)
    if decision is not None and not _second_person_satisfied(db, ev, decision):
        return None              # QA-044: one signature of two answers nothing
    if decision is None or not escalated:
        return decision
    raised = db.execute(
        select(M.Escalation.created_at).where(
            M.Escalation.finding_id == ev.finding_id, M.Escalation.withdrawn_at.is_(None))
    ).scalars().first()
    return decision if raised is None or decision.created_at >= raised else None


def requires_second_person(db: DBSession, ev: M.Evaluation) -> bool:
    """Step 31 r15 / F-2 (QA-044, 2026-10-30): whether this point's standard, as the
    Review pinned it, requires an independent second approval — the configuration key
    ``requires_second_person``. Read from the snapshot, so publishing a change never
    alters a Review already under way (rule 16)."""
    config = db.execute(
        select(M.CompanyStandardVersion.configuration)
        .join(M.ConfigurationSnapshotItem, M.ConfigurationSnapshotItem
              .company_standard_version_id == M.CompanyStandardVersion.id)
        .join(M.Review, M.Review.configuration_snapshot_id
              == M.ConfigurationSnapshotItem.snapshot_id)
        .join(M.Finding, (M.Finding.review_id == M.Review.id) & (
            M.Finding.requirement_version_id
            == M.ConfigurationSnapshotItem.requirement_version_id))
        .where(M.Finding.id == ev.finding_id)).scalar()
    return bool((config or {}).get("requires_second_person"))


def own_contract(db: DBSession, ev: M.Evaluation, user_id: UUID) -> bool:
    """`AM-289` r1 (reversing AM-170 O2): ``user_id`` owns or created the contract this
    Evaluation belongs to, so their decision on it takes effect only once a second,
    different holder of `legal.decision` confirms it. House policy and
    segregation-of-duties practice (r4), not law."""
    contract_id = db.execute(
        select(M.Review.contract_id)
        .join(M.Finding, M.Finding.review_id == M.Review.id)
        .where(M.Finding.id == ev.finding_id)).scalar_one_or_none()
    return contract_id is not None and user_id in contract_principals(db, contract_id)


def second_person_needed(db: DBSession, ev: M.Evaluation, decided_by: UUID) -> bool:
    """Whether a decision by ``decided_by`` needs a co-signature: the standard sets
    ``requires_second_person`` (F-2, QA-044), or it is their own contract (`AM-289`)."""
    return requires_second_person(db, ev) or own_contract(db, ev, decided_by)


def _second_person_satisfied(db: DBSession, ev: M.Evaluation,
                             current: M.LegalDecision) -> bool:
    """Co-signature within the append-only chain (F-2): the current decision and the one
    before it share a type and have different actors. A clarification never needs it."""
    if (current.decision_type is DecisionType.REQUEST_CLARIFICATION
            or not second_person_needed(db, ev, current.decided_by)):
        return True
    previous = db.execute(
        select(M.LegalDecision).where(
            M.LegalDecision.evaluation_id == ev.id,
            M.LegalDecision.version_number == current.version_number - 1)).scalar()
    return (previous is not None and previous.decision_type is current.decision_type
            and previous.decided_by != current.decided_by)


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
        decision = effective_decision(db, ev, escalated)
        if decision is None:
            return False
        if decision.decision_type is DecisionType.REQUEST_CLARIFICATION:
            # Step 31 r10 — leaves the workflow unresolved until completed.
            return False
    return True


#: `AM-299` r3: the deal owner's acceptance of a change "Better for us" / "No change for
#: us", carried onto our reply's own Finding (`analysis.negotiation.carry_acceptances`).
#: The audit row IS the record — append-only, attributed — and never a Legal Decision.
OWNER_ACCEPTANCE_CARRIED = "negotiation.acceptance_carried"


#: `AM-317` r7 (owner, 2026-11-09, option a): a Legal Decision on an earlier version of
#: the same contract stands for this Finding — byte-identical text read (spacing aside)
#: against the same standard version (`workflow.decisions.carry_forward`). The audit row
#: IS the record; no Legal Decision is copied, and an escalation reopens the point.
DECISION_CARRIED_FORWARD = "decision.carried_forward"


def carried_forward(db: DBSession, finding_id: UUID) -> dict | None:
    """The carry record's after-state, or None."""
    return db.execute(select(M.AuditEvent.after_state).where(
        M.AuditEvent.action == DECISION_CARRIED_FORWARD,
        M.AuditEvent.entity_type == "finding",
        M.AuditEvent.entity_id == finding_id).limit(1)).scalar()


def owner_accepted(db: DBSession, finding_id: UUID) -> bool:
    return db.execute(select(M.AuditEvent.id).where(
        M.AuditEvent.action == OWNER_ACCEPTANCE_CARRIED,
        M.AuditEvent.entity_type == "finding",
        M.AuditEvent.entity_id == finding_id).limit(1)).first() is not None


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
        decision = effective_decision(db, ev, escalated)
        if decision is None:
            needs_decision = True
        elif decision.decision_type is DecisionType.REQUEST_CLARIFICATION:
            outstanding_clarification = True

    if outstanding_clarification:
        return FindingStatus.AWAITING_CLARIFICATION
    if needs_decision and not owner_accepted(db, finding.id) \
            and (escalated or carried_forward(db, finding.id) is None):  # AM-317 r7
        return FindingStatus.DECISION_REQUIRED
    if any(evaluation_requires_decision(
            classification=ev.classification, rule_outcome=ev.rule_outcome,
            requirement_required=requirement_required, escalated=escalated)
           for ev in evaluations):
        return FindingStatus.RESOLVED
    # Nothing ever required a decision. OPEN is terminal-but-actionable:
    # escalation can still move it to DECISION_REQUIRED (D-4.1).
    return FindingStatus.OPEN
