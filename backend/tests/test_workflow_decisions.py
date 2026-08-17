"""Decision, escalation and Review lifecycle — locked Steps 4, 22, 30, 31, AB-1."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select, text

from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.domain.enums import (
    DecisionType as D,
    FindingStatus,
    ReviewStatus as RS,
    RuleOutcome as O,
)
from legalmind.evaluation.registry import evaluate
from legalmind.evaluation.service import persist_evaluation
from legalmind.security import audit as A
from legalmind.security import permissions as P
from legalmind.security.errors import Forbidden, NotVisible
from legalmind.security.resolver import has_permission
from legalmind.workflow.decisions import (
    decision_history,
    decision_is_effective,
    record_decision,
    require_effective_decision,
)
from legalmind.workflow.errors import (
    InvalidTransition,
    SecondPersonRequired,
    VersionConflict,
)
from legalmind.workflow.escalation import (
    escalate_finding,
    is_escalated,
    withdraw_escalation,
)
from legalmind.workflow.review_lifecycle import (
    advance_after_analysis,
    all_required_decisions_complete,
    requires_legal_review,
    transition,
)
from tests.conftest import grant_role, make_review_for, make_user
from tests.evaluation_fixtures import cap, multi_scope_rule, numeric_input


@pytest.fixture
def case(db, seeded):
    """Owner + Review + a Finding whose single Evaluation requires a decision."""
    owner = make_user(db)
    grant_role(db, owner, P.ROLE_USER)
    review = make_review_for(db, owner)

    req = M.Requirement(code=f"W-{uuid.uuid4().hex[:6]}",
                        status=E.ConfigStatus.ACTIVE)
    db.add(req); db.flush()
    rv = M.RequirementVersion(
        requirement_id=req.id, version_number=1, name="Structural",
        evaluator_type=E.EvaluatorType.NUMERIC_COMPARISON, created_by=owner.id)
    db.add(rv); db.flush()

    run = M.DocumentProcessingRun(
        document_version_id=review.document_version_id,
        run_type=E.ProcessingRunType.PARSE,
        status=E.ProcessingRunStatus.COMPLETED)
    db.add(run); db.flush()
    ev = M.DocumentEvidence(
        document_version_id=review.document_version_id,
        processing_run_id=run.id, content="structural clause",
        source_type=E.EvidenceSourceType.NATIVE_TEXT)
    db.add(ev); db.flush()

    out = evaluate(numeric_input([cap(24, evidence=(ev.id,))]))  # APPROVAL_REQUIRED
    persisted = persist_evaluation(db, review=review,
                                   requirement_version_id=rv.id, output=out)
    db.flush()
    return owner, review, persisted


def legal_user(db, review, *, with_authority=True, extra=None):
    """A Legal Reviewer assigned to the Review (Step 24 r6)."""
    u = make_user(db)
    grant_role(db, u, P.ROLE_LEGAL_REVIEWER)
    if with_authority:
        grant_role(db, u, P.ROLE_LEGAL_DECISION_AUTHORITY)
    if extra:
        grant_role(db, u, extra)
    db.add(M.ReviewAssignment(review_id=review.id, user_id=u.id,
                              assigned_by=review.created_by))
    db.flush()
    return u


# ================================================== authority (SEC-02, SEC-05)
def test_decision_requires_explicit_legal_authority(db, case):
    """Locked Step 23 — decisions only "when explicitly permitted"."""
    owner, review, p = case
    reviewer = legal_user(db, review, with_authority=False)
    with pytest.raises(Forbidden, match="legal.decision"):
        record_decision(db, actor_id=reviewer.id,
                        evaluation_id=p.evaluations[0].id,
                        decision_type=D.ACCEPT_DEVIATION, justification="x")


def test_super_admin_cannot_decide(db, case):
    """SEC-02 — no bypass reaches legal authority, and Step 24 r8 means a Super
    Admin cannot even see the Review."""
    owner, review, p = case
    sa = make_user(db)
    grant_role(db, sa, P.ROLE_SUPER_ADMIN)
    with pytest.raises(NotVisible):
        record_decision(db, actor_id=sa.id, evaluation_id=p.evaluations[0].id,
                        decision_type=D.ACCEPT_DEVIATION, justification="x")


def test_normal_user_cannot_decide_on_own_review(db, case):
    """ROLE-03 — a User can escalate but never decide, even on their own Review."""
    owner, review, p = case
    with pytest.raises(Forbidden, match="legal.decision"):
        record_decision(db, actor_id=owner.id, evaluation_id=p.evaluations[0].id,
                        decision_type=D.ACCEPT_DEVIATION, justification="x")


def test_approve_customization_needs_the_additional_permission(db, case):
    """Step 23 / 47.5 — legal.decision alone is not enough.

    The seeded LEGAL_DECISION_AUTHORITY role bundles both permissions, matching
    Step 23 ("A selected Legal user may additionally have: legal.decision,
    legal.approve_customization"). A deployment may grant them separately, so
    this builds a narrower role to exercise the service-level separation.
    """
    owner, review, p = case
    reviewer = make_user(db)
    grant_role(db, reviewer, P.ROLE_LEGAL_REVIEWER)
    narrow = M.Role(code=f"DECIDE_ONLY_{uuid.uuid4().hex[:6]}", name="Decide only")
    db.add(narrow); db.flush()
    decide = db.execute(
        select(M.Permission).where(M.Permission.name == P.LEGAL_DECISION)
    ).scalar_one()
    db.add(M.RolePermission(role_id=narrow.id, permission_id=decide.id))
    db.add(M.UserRole(user_id=reviewer.id, role_id=narrow.id))
    db.add(M.ReviewAssignment(review_id=review.id, user_id=reviewer.id,
                              assigned_by=review.created_by))
    db.flush()
    assert has_permission(db, reviewer.id, P.LEGAL_DECISION) is True
    assert has_permission(db, reviewer.id, P.LEGAL_APPROVE_CUSTOMIZATION) is False

    with pytest.raises(Forbidden, match="approve_customization"):
        record_decision(db, actor_id=reviewer.id,
                        evaluation_id=p.evaluations[0].id,
                        decision_type=D.APPROVE_CUSTOMIZATION,
                        justification="x")


def test_denied_attempt_is_audited(db, case):
    """SEC-09 — a refused decision attempt leaves a record."""
    owner, review, p = case
    reviewer = legal_user(db, review, with_authority=False)
    with pytest.raises(Forbidden):
        record_decision(db, actor_id=reviewer.id,
                        evaluation_id=p.evaluations[0].id,
                        decision_type=D.ACCEPT_DEVIATION, justification="x")
    actions = db.execute(select(M.AuditEvent.action)).scalars().all()
    assert A.AUTHZ_PERMISSION_DENIED in actions


def test_justification_is_mandatory(db, case):
    """Step 31 r11. Whitespace-only is rejected here; the column enforces NOT NULL."""
    owner, review, p = case
    reviewer = legal_user(db, review)
    with pytest.raises(Forbidden, match="justification"):
        record_decision(db, actor_id=reviewer.id,
                        evaluation_id=p.evaluations[0].id,
                        decision_type=D.ACCEPT_DEVIATION, justification="   ")


# ============================================== versioning (AM-12, Step 31 r14)
def test_decision_is_recorded_and_finding_resolves(db, case):
    owner, review, p = case
    reviewer = legal_user(db, review)
    result = record_decision(db, actor_id=reviewer.id,
                             evaluation_id=p.evaluations[0].id,
                             decision_type=D.ACCEPT_DEVIATION,
                             justification="structural test")
    assert result.decision.version_number == 1
    assert result.is_effective is True
    assert result.finding_status == FindingStatus.RESOLVED.value


def test_supersession_appends_a_new_version(db, case):
    owner, review, p = case
    reviewer = legal_user(db, review)
    ev_id = p.evaluations[0].id
    record_decision(db, actor_id=reviewer.id, evaluation_id=ev_id,
                    decision_type=D.ACCEPT_DEVIATION, justification="v1")
    record_decision(db, actor_id=reviewer.id, evaluation_id=ev_id,
                    decision_type=D.REJECT, justification="v2")
    chain = decision_history(db, ev_id)
    assert [d.version_number for d in chain] == [1, 2]
    assert chain[0].decision_type is D.ACCEPT_DEVIATION      # v1 intact
    assert chain[0].justification == "v1"


def test_stale_expected_version_is_a_conflict(db, case):
    """49.7 — optimistic concurrency comes from the UNIQUE constraint, surfaced
    as 409 rather than an internal error."""
    owner, review, p = case
    reviewer = legal_user(db, review)
    ev_id = p.evaluations[0].id
    record_decision(db, actor_id=reviewer.id, evaluation_id=ev_id,
                    decision_type=D.ACCEPT_DEVIATION, justification="v1")
    with pytest.raises(VersionConflict) as exc:
        record_decision(db, actor_id=reviewer.id, evaluation_id=ev_id,
                        decision_type=D.REJECT, justification="v2",
                        expected_version=0)     # thinks nothing exists yet
    assert exc.value.status_code == 409


def test_there_is_no_finding_level_decision_entry_point(db):
    """AB-1.1 / 49.7 — a decision resolves exactly one Evaluation."""
    import inspect
    params = set(inspect.signature(record_decision).parameters)
    assert "evaluation_id" in params
    assert "finding_id" not in params


def test_decision_on_one_scope_leaves_the_other_open(db, seeded):
    """AB-1.1 — never implicitly disposes of another Evaluation."""
    owner = make_user(db); grant_role(db, owner, P.ROLE_USER)
    review = make_review_for(db, owner)
    req = M.Requirement(code=f"W-{uuid.uuid4().hex[:6]}",
                        status=E.ConfigStatus.ACTIVE)
    db.add(req); db.flush()
    rv = M.RequirementVersion(
        requirement_id=req.id, version_number=1, name="S",
        evaluator_type=E.EvaluatorType.NUMERIC_COMPARISON, created_by=owner.id)
    db.add(rv); db.flush()
    run = M.DocumentProcessingRun(
        document_version_id=review.document_version_id,
        run_type=E.ProcessingRunType.PARSE,
        status=E.ProcessingRunStatus.COMPLETED)
    db.add(run); db.flush()
    ids = []
    for _ in range(2):
        e = M.DocumentEvidence(document_version_id=review.document_version_id,
                               processing_run_id=run.id, content="c",
                               source_type=E.EvidenceSourceType.NATIVE_TEXT)
        db.add(e); db.flush(); ids.append(e.id)

    out = evaluate(numeric_input([
        cap(24, evidence=(ids[0],)),
        cap(None, status="UNLIMITED", scope="SCOPE_B",
            kind=E.EvaluationKind.EXCEPTION, label="x", evidence=(ids[1],)),
    ], rule=multi_scope_rule("SCOPE_B")))
    p = persist_evaluation(db, review=review, requirement_version_id=rv.id,
                           output=out)
    reviewer = legal_user(db, review)
    record_decision(db, actor_id=reviewer.id, evaluation_id=p.evaluations[0].id,
                    decision_type=D.ACCEPT_DEVIATION, justification="one scope")
    assert db.get(M.Finding, p.finding.id).status is FindingStatus.DECISION_REQUIRED


# ============================================ second-person approval (r15, F-2)
def test_second_person_approval_requires_a_different_actor(db, case):
    owner, review, p = case
    first = legal_user(db, review)
    ev_id = p.evaluations[0].id

    r1 = record_decision(db, actor_id=first.id, evaluation_id=ev_id,
                         decision_type=D.ACCEPT_DEVIATION, justification="v1",
                         requires_second_person=True)
    assert r1.is_effective is False
    with pytest.raises(SecondPersonRequired):
        require_effective_decision(db, ev_id, requires_second_person=True)

    # The same person repeating themselves is not independent approval.
    r2 = record_decision(db, actor_id=first.id, evaluation_id=ev_id,
                         decision_type=D.ACCEPT_DEVIATION, justification="again",
                         requires_second_person=True)
    assert r2.is_effective is False

    second = legal_user(db, review)
    r3 = record_decision(db, actor_id=second.id, evaluation_id=ev_id,
                         decision_type=D.ACCEPT_DEVIATION, justification="co-sign",
                         requires_second_person=True)
    assert r3.is_effective is True


def test_second_person_must_agree_on_the_decision_type(db, case):
    owner, review, p = case
    a, b = legal_user(db, review), legal_user(db, review)
    ev_id = p.evaluations[0].id
    record_decision(db, actor_id=a.id, evaluation_id=ev_id,
                    decision_type=D.ACCEPT_DEVIATION, justification="v1",
                    requires_second_person=True)
    r = record_decision(db, actor_id=b.id, evaluation_id=ev_id,
                        decision_type=D.REJECT, justification="disagrees",
                        requires_second_person=True)
    assert r.is_effective is False


def test_request_clarification_is_never_effective(db, case):
    """Step 31 r10 — leaves the workflow unresolved until completed."""
    owner, review, p = case
    reviewer = legal_user(db, review)
    ev_id = p.evaluations[0].id
    record_decision(db, actor_id=reviewer.id, evaluation_id=ev_id,
                    decision_type=D.REQUEST_CLARIFICATION,
                    justification="need detail")
    assert decision_is_effective(db, ev_id, requires_second_person=False) is False
    assert db.get(M.Finding, p.finding.id).status is \
        FindingStatus.AWAITING_CLARIFICATION


# ====================================================== escalation (Step 4, F-3)
def test_normal_user_may_escalate(db, case):
    """ROLE-03 / Step 4 — escalation is a request for review, not approval."""
    owner, review, p = case
    esc = escalate_finding(db, actor_id=owner.id, finding_id=p.finding.id,
                           reason="please review")
    assert esc.raised_by == owner.id
    assert is_escalated(db, p.finding.id) is True


def test_escalation_is_not_approval(db, case):
    """Step 4 — it must not dispose of anything."""
    owner, review, p = case
    escalate_finding(db, actor_id=owner.id, finding_id=p.finding.id,
                     reason="please review")
    assert decision_history(db, p.evaluations[0].id) == []
    assert db.get(M.Finding, p.finding.id).status is FindingStatus.DECISION_REQUIRED


def test_escalation_makes_a_match_require_a_decision(db, seeded):
    """D-3.5(d) / F-3 — escalation marks every Evaluation under the Finding."""
    owner = make_user(db); grant_role(db, owner, P.ROLE_USER)
    review = make_review_for(db, owner)
    req = M.Requirement(code=f"W-{uuid.uuid4().hex[:6]}",
                        status=E.ConfigStatus.ACTIVE)
    db.add(req); db.flush()
    rv = M.RequirementVersion(requirement_id=req.id, version_number=1, name="S",
                              evaluator_type=E.EvaluatorType.NUMERIC_COMPARISON,
                              created_by=owner.id)
    db.add(rv); db.flush()
    run = M.DocumentProcessingRun(
        document_version_id=review.document_version_id,
        run_type=E.ProcessingRunType.PARSE,
        status=E.ProcessingRunStatus.COMPLETED)
    db.add(run); db.flush()
    e = M.DocumentEvidence(document_version_id=review.document_version_id,
                           processing_run_id=run.id, content="c",
                           source_type=E.EvidenceSourceType.NATIVE_TEXT)
    db.add(e); db.flush()

    out = evaluate(numeric_input([cap(10, evidence=(e.id,))]))   # MATCH
    p = persist_evaluation(db, review=review, requirement_version_id=rv.id,
                           output=out)
    assert p.finding.status is FindingStatus.OPEN

    escalate_finding(db, actor_id=owner.id, finding_id=p.finding.id,
                     reason="unhappy with this")
    assert db.get(M.Finding, p.finding.id).status is FindingStatus.DECISION_REQUIRED

    withdraw_escalation(db, actor_id=owner.id, finding_id=p.finding.id)
    assert db.get(M.Finding, p.finding.id).status is FindingStatus.OPEN


def test_stranger_cannot_escalate_another_users_finding(db, case):
    owner, review, p = case
    stranger = make_user(db); grant_role(db, stranger, P.ROLE_USER)
    with pytest.raises(NotVisible):
        escalate_finding(db, actor_id=stranger.id, finding_id=p.finding.id,
                         reason="nosy")


def test_escalation_is_audited(db, case):
    owner, review, p = case
    escalate_finding(db, actor_id=owner.id, finding_id=p.finding.id, reason="r")
    actions = db.execute(select(M.AuditEvent.action)).scalars().all()
    assert A.LEGAL_FINDING_ESCALATED in actions


# ================================================ Review lifecycle (Step 30)
def test_only_locked_transitions_are_permitted(db, case):
    owner, review, p = case
    review.status = RS.DRAFT
    db.flush()
    with pytest.raises(InvalidTransition):
        transition(db, review, RS.RESOLVED)          # DRAFT -> RESOLVED forbidden
    transition(db, review, RS.UPLOADED)              # permitted
    assert review.status is RS.UPLOADED


def test_terminal_states_have_no_exits(db, case):
    owner, review, p = case
    for terminal in (RS.CLOSED, RS.ANALYSIS_FAILED, RS.CANCELLED):
        review.status = terminal
        db.flush()
        with pytest.raises(InvalidTransition):
            transition(db, review, RS.RESOLVED)


def test_cannot_resolve_while_a_decision_is_outstanding(db, case):
    """Step 30 r7 / Step 31 r18 — RESOLVED is derived, never asserted."""
    owner, review, p = case
    review.status = RS.LEGAL_REVIEW
    db.flush()
    assert all_required_decisions_complete(db, review) is False
    with pytest.raises(InvalidTransition, match="still require a Legal Decision"):
        transition(db, review, RS.RESOLVED)


def test_resolves_once_the_decision_is_recorded(db, case):
    owner, review, p = case
    reviewer = legal_user(db, review)
    record_decision(db, actor_id=reviewer.id, evaluation_id=p.evaluations[0].id,
                    decision_type=D.ACCEPT_DEVIATION, justification="ok")
    review.status = RS.LEGAL_REVIEW
    db.flush()
    transition(db, review, RS.RESOLVED)
    assert review.status is RS.RESOLVED


def test_resolved_does_not_change_the_finding_classification(db, case):
    """RESOLVED != MATCH (Step 22 clarification, Step 30 r8)."""
    owner, review, p = case
    before = db.get(M.Finding, p.finding.id).classification
    reviewer = legal_user(db, review)
    record_decision(db, actor_id=reviewer.id, evaluation_id=p.evaluations[0].id,
                    decision_type=D.ACCEPT_DEVIATION, justification="ok")
    review.status = RS.LEGAL_REVIEW
    db.flush()
    transition(db, review, RS.RESOLVED)
    assert db.get(M.Finding, p.finding.id).classification is before
    assert db.get(M.Finding, p.finding.id).classification is not \
        E.FindingClassification.MATCH


def test_advance_after_analysis_enters_legal_review_only_when_required(db, case):
    """Step 30 r6 — the workflow decides, not the caller."""
    owner, review, p = case
    review.status = RS.PROCESSING
    db.flush()
    assert requires_legal_review(db, review) is True
    assert advance_after_analysis(db, review) is RS.LEGAL_REVIEW


def test_advance_after_analysis_resolves_when_nothing_is_required(db, seeded):
    owner = make_user(db); grant_role(db, owner, P.ROLE_USER)
    review = make_review_for(db, owner)
    req = M.Requirement(code=f"W-{uuid.uuid4().hex[:6]}",
                        status=E.ConfigStatus.ACTIVE)
    db.add(req); db.flush()
    rv = M.RequirementVersion(requirement_id=req.id, version_number=1, name="S",
                              evaluator_type=E.EvaluatorType.NUMERIC_COMPARISON,
                              created_by=owner.id)
    db.add(rv); db.flush()
    run = M.DocumentProcessingRun(
        document_version_id=review.document_version_id,
        run_type=E.ProcessingRunType.PARSE,
        status=E.ProcessingRunStatus.COMPLETED)
    db.add(run); db.flush()
    e = M.DocumentEvidence(document_version_id=review.document_version_id,
                           processing_run_id=run.id, content="c",
                           source_type=E.EvidenceSourceType.NATIVE_TEXT)
    db.add(e); db.flush()
    out = evaluate(numeric_input([cap(10, evidence=(e.id,))]))   # MATCH
    persist_evaluation(db, review=review, requirement_version_id=rv.id, output=out)
    review.status = RS.PROCESSING
    db.flush()
    assert advance_after_analysis(db, review) is RS.RESOLVED


def test_analysis_failed_is_distinct_from_unable_to_evaluate(db, case):
    """Step 30 r13 — a Review-level failure is not a Finding classification."""
    owner, review, p = case
    review.status = RS.PROCESSING
    db.flush()
    transition(db, review, RS.ANALYSIS_FAILED)
    assert review.status is RS.ANALYSIS_FAILED
    assert db.get(M.Finding, p.finding.id).classification is not \
        E.FindingClassification.UNABLE_TO_EVALUATE


def test_every_transition_is_audited(db, case):
    """Step 30 r17."""
    owner, review, p = case
    review.status = RS.DRAFT
    db.flush()
    transition(db, review, RS.UPLOADED, actor_id=owner.id, request_id="req-1")
    events = db.execute(
        select(M.AuditEvent).where(M.AuditEvent.action == A.REVIEW_STATUS_CHANGED)
    ).scalars().all()
    assert events
    latest = events[-1]
    assert latest.before_state["status"] == "DRAFT"
    assert latest.after_state["status"] == "UPLOADED"
    assert latest.event_metadata["request_id"] == "req-1"
