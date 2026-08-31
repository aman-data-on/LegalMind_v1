"""Evaluation persistence and workflow — locked AB-1, EV-MIN, D-3.5, D-3.6, J-4."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.domain.enums import (
    DecisionType,
    FindingStatus,
)
from legalmind.domain.enums import (
    FindingClassification as C,
)
from legalmind.domain.enums import (
    RuleOutcome as O,
)
from legalmind.evaluation.registry import evaluate
from legalmind.evaluation.service import (
    EvidenceCardinalityViolation,
    persist_evaluation,
)
from legalmind.evaluation.workflow import (
    current_decision,
    derive_finding_status,
    evaluation_requires_decision,
    finding_is_resolved,
)
from tests.conftest import make_review_for, make_user
from tests.evaluation_fixtures import (
    cap,
    multi_scope_rule,
    numeric_input,
    structural_standard,
)


@pytest.fixture
def scenario(db):
    """A Review plus a NUMERIC_COMPARISON Requirement version."""
    user = make_user(db)
    review = make_review_for(db, user)
    req = M.Requirement(code=f"STRUCT-{uuid.uuid4().hex[:6]}",
                        status=E.ConfigStatus.ACTIVE)
    db.add(req); db.flush()
    rv = M.RequirementVersion(
        requirement_id=req.id, version_number=1, name="Structural",
        evaluator_type=E.EvaluatorType.NUMERIC_COMPARISON, created_by=user.id)
    db.add(rv); db.flush()
    return user, review, rv


def _evidence(db, review):
    """A real document_evidence row so evidence FKs resolve."""
    run = M.DocumentProcessingRun(
        document_version_id=review.document_version_id,
        run_type=E.ProcessingRunType.PARSE,
        status=E.ProcessingRunStatus.COMPLETED)
    db.add(run); db.flush()
    ev = M.DocumentEvidence(
        document_version_id=review.document_version_id,
        processing_run_id=run.id, content="structural clause text",
        source_type=E.EvidenceSourceType.NATIVE_TEXT)
    db.add(ev); db.flush()
    return ev


# ================================================================== EV-MIN
def test_persisted_finding_always_has_at_least_one_evaluation(db, scenario):
    user, review, rv = scenario
    ev = _evidence(db, review)
    out = evaluate(numeric_input([cap(10, evidence=(ev.id,))]))
    persisted = persist_evaluation(db, review=review,
                                   requirement_version_id=rv.id, output=out)
    db.execute(select(M.Finding))          # force flush
    db.flush()
    db.execute(__import__("sqlalchemy").text("SET CONSTRAINTS ALL IMMEDIATE"))
    assert len(persisted.evaluations) >= 1


def test_missing_finding_persists_with_zero_evidence(db, scenario):
    """N-34 — a wholly absent provision yields MISSING with no evidence rows,
    and the database permits it (no minimum-cardinality constraint)."""
    user, review, rv = scenario
    out = evaluate(numeric_input([]))
    persisted = persist_evaluation(db, review=review,
                                   requirement_version_id=rv.id, output=out)
    db.flush()
    db.execute(__import__("sqlalchemy").text("SET CONSTRAINTS ALL IMMEDIATE"))
    assert persisted.finding.classification is C.MISSING
    count = db.execute(
        select(__import__("sqlalchemy").func.count(M.EvaluationEvidence.evidence_id))
        .where(M.EvaluationEvidence.evaluation_id == persisted.evaluations[0].id)
    ).scalar_one()
    assert count == 0


def test_non_missing_without_evidence_is_refused(db, scenario):
    """N-34 — the alternative failure mode is fabricating evidence, which
    locked 45C.25 forbids. So this refuses loudly instead."""
    user, review, rv = scenario
    out = evaluate(numeric_input([cap(10, evidence=())]))
    assert out.evaluations[0].classification is C.MATCH
    with pytest.raises(EvidenceCardinalityViolation):
        persist_evaluation(db, review=review, requirement_version_id=rv.id,
                           output=out)


# ============================================== scoped evaluations + roll-up
def test_scoped_evaluations_persist_with_derived_roll_up(db, scenario):
    user, review, rv = scenario
    e1, e2 = _evidence(db, review), _evidence(db, review)
    out = evaluate(numeric_input([
        cap(10, evidence=(e1.id,)),
        cap(None, status="UNLIMITED", scope="SCOPE_B",
            kind=E.EvaluationKind.EXCEPTION, label="carve-out",
            evidence=(e2.id,)),
    ], rule=multi_scope_rule("SCOPE_B")))
    p = persist_evaluation(db, review=review, requirement_version_id=rv.id,
                           output=out)
    db.flush()
    db.execute(__import__("sqlalchemy").text("SET CONSTRAINTS ALL IMMEDIATE"))

    assert len(p.evaluations) == 2
    assert p.finding.classification is C.DEVIATION          # derived roll-up
    outcomes = {e.rule_outcome for e in p.evaluations}
    assert O.UNACCEPTABLE in outcomes                        # per-scope preserved
    assert O.NOT_APPLICABLE in outcomes


def test_rule_outcome_lives_only_on_evaluations(db, scenario):
    """J-2 — no Finding-level rule outcome is persisted."""
    user, review, rv = scenario
    ev = _evidence(db, review)
    out = evaluate(numeric_input([cap(24, evidence=(ev.id,))]))
    p = persist_evaluation(db, review=review, requirement_version_id=rv.id,
                           output=out)
    assert not hasattr(p.finding, "rule_outcome")
    assert p.evaluations[0].rule_outcome is O.UNACCEPTABLE  # the blanket rule (AM-33)


def test_evaluator_and_rule_versions_are_persisted(db, scenario):
    """AM-19 / AM-20 — reproducibility. Step 32 audit q4 becomes answerable."""
    user, review, rv = scenario
    ev = _evidence(db, review)
    legal_rule_version = M.LegalRuleVersion(
        requirement_version_id=rv.id, version_number=1,
        rule_type=E.RuleType.THRESHOLD, configuration={"acceptable_max": 20},
        created_by=user.id)
    db.add(legal_rule_version); db.flush()

    out = evaluate(numeric_input([cap(10, evidence=(ev.id,))]))
    p = persist_evaluation(db, review=review, requirement_version_id=rv.id,
                           output=out,
                           legal_rule_version_id=legal_rule_version.id)
    stored = p.evaluations[0]
    assert stored.evaluator_version == "NUMERIC-COMPARISON-v1"
    assert stored.legal_rule_version_id == legal_rule_version.id


def test_diagnostics_persisted_but_cannot_alter_the_finding(db, scenario):
    """REC-07 — diagnostic metadata only."""
    user, review, rv = scenario
    out = evaluate(numeric_input(
        [], extraction_status=E.ExtractionStatus.COMPLETE))
    p = persist_evaluation(db, review=review, requirement_version_id=rv.id,
                           output=out)
    stored = p.evaluations[0]
    assert "diagnostics" in stored.result
    assert stored.classification is C.MISSING       # unchanged by diagnostics


# ======================================================= D-3.5 requires-decision
@pytest.mark.parametrize("outcome,expected", [
    (O.ACCEPTABLE, False),
    # NOT_APPLICABLE was False until 2026-08-18; see the policy test below.
    (O.NOT_APPLICABLE, True),
    (O.APPROVAL_REQUIRED, True),
    (O.UNACCEPTABLE, True),
])
def test_decision_required_by_rule_outcome(outcome, expected):
    assert evaluation_requires_decision(
        classification=C.DEVIATION, rule_outcome=outcome,
        requirement_required=True) is expected


def test_an_unruled_deviation_is_routed_to_a_human():
    """The owner's V1 fail-closed policy of 2026-08-18, and why it exists.

    No approved Legal Rule exists, so nothing can tell LegalMind whether a
    deviation is acceptable, needs approval, or is unacceptable. The owner's
    instruction: the outcome stays NOT_APPLICABLE **and** it goes to human Legal
    review.

    D-3.5's four baseline conditions do not cover it — DEVIATION is Tier 2 — so
    before this the Finding derived to OPEN, which means "nothing ever required a
    decision". That contradicted locked Step 20 r4's own words, that with no rule
    "the deviation stands and a human decides". F-4 permits configuration to WIDEN
    the set and never to narrow it, which is what this is.
    """
    assert evaluation_requires_decision(
        classification=C.DEVIATION, rule_outcome=O.NOT_APPLICABLE,
        requirement_required=True) is True


def test_the_policy_widens_and_never_narrows():
    """The guard that matters: (e) must not make anything require LESS review.

    A MATCH that no rule dispositioned is not a deviation and must stay out of
    the decision queue, or every clean Finding would demand a Legal Decision.
    """
    assert evaluation_requires_decision(
        classification=C.MATCH, rule_outcome=O.NOT_APPLICABLE,
        requirement_required=True) is False
    # And an ACCEPTABLE deviation — one a rule DID disposition — stays out too.
    assert evaluation_requires_decision(
        classification=C.DEVIATION, rule_outcome=O.ACCEPTABLE,
        requirement_required=True) is False


@pytest.mark.parametrize("classification", [
    C.UNABLE_TO_EVALUATE, C.CONFLICT, C.AMBIGUOUS, C.UNRESOLVED])
def test_tier_1_always_requires_a_decision(classification):
    assert evaluation_requires_decision(
        classification=classification, rule_outcome=O.NOT_APPLICABLE,
        requirement_required=True) is True


def test_required_missing_requires_a_decision_optional_does_not():
    assert evaluation_requires_decision(
        classification=C.MISSING, rule_outcome=O.NOT_APPLICABLE,
        requirement_required=True) is True
    assert evaluation_requires_decision(
        classification=C.MISSING, rule_outcome=O.NOT_APPLICABLE,
        requirement_required=False) is False


def test_escalation_requires_a_decision_even_when_acceptable():
    """D-3.5(d) / F-3 — escalation is a user request for review."""
    assert evaluation_requires_decision(
        classification=C.MATCH, rule_outcome=O.NOT_APPLICABLE,
        requirement_required=True, escalated=True) is True


def _with_outcome(out, scope_key, outcome):
    """Rebuild frozen evaluator output with one scope's outcome replaced.

    AM-33: no authorized rule form emits ACCEPTABLE on a deviation, but the
    locked B-3 workflow semantics govern the outcome AXIS — historical rows
    included — so these tests construct the vocabulary value directly.
    """
    import dataclasses
    evaluations = [
        dataclasses.replace(entry, rule_outcome=outcome)
        if entry.scope_key == scope_key else entry
        for entry in out.evaluations
    ]
    return dataclasses.replace(out, evaluations=type(out.evaluations)(evaluations))


def test_match_acceptable_does_not_block_resolution(db, scenario):
    """The B-3 scenario: MATCH and ACCEPTABLE scopes are satisfied trivially."""
    user, review, rv = scenario
    e1, e2 = _evidence(db, review), _evidence(db, review)
    out = evaluate(numeric_input([
        cap(10, evidence=(e1.id,)),                               # MATCH
        cap(20, scope="SCOPE_B", evidence=(e2.id,)),              # DEVIATION
    ], rule=multi_scope_rule("SCOPE_B")))
    out = _with_outcome(out, "SCOPE_B", O.ACCEPTABLE)  # see _with_outcome (AM-33)
    p = persist_evaluation(db, review=review, requirement_version_id=rv.id,
                           output=out)
    db.flush()
    assert finding_is_resolved(db, p.finding) is True
    assert derive_finding_status(db, p.finding) is FindingStatus.OPEN


# ============================================ D-3.6 heterogeneous resolution
def test_finding_blocked_until_the_unacceptable_scope_is_decided(db, scenario):
    """The locked B-3 worked example.

    MATCH + UNACCEPTABLE + ACCEPTABLE. The Finding stays DECISION_REQUIRED until
    the unacceptable scope receives a decision — and a decision on it must not
    dispose of the others implicitly (AB-1.1).
    """
    user, review, rv = scenario
    e1, e2, e3 = (_evidence(db, review) for _ in range(3))
    out = evaluate(numeric_input([
        cap(10, evidence=(e1.id,)),                                        # MATCH
        cap(None, status="UNLIMITED", scope="SCOPE_B",
            kind=E.EvaluationKind.EXCEPTION, label="confidentiality",
            evidence=(e2.id,)),                                    # UNACCEPTABLE
        cap(20, scope="SCOPE_C", kind=E.EvaluationKind.EXCEPTION,
            label="ip", evidence=(e3.id,)),                           # DEVIATION
    ], rule=multi_scope_rule("SCOPE_B", "SCOPE_C")))
    out = _with_outcome(out, "SCOPE_C", O.ACCEPTABLE)  # see _with_outcome (AM-33)
    p = persist_evaluation(db, review=review, requirement_version_id=rv.id,
                           output=out)
    db.flush()

    assert p.finding.classification is C.DEVIATION
    assert finding_is_resolved(db, p.finding) is False
    assert derive_finding_status(db, p.finding) is FindingStatus.DECISION_REQUIRED

    unacceptable = next(e for e in p.evaluations
                        if e.rule_outcome is O.UNACCEPTABLE)
    db.add(M.LegalDecision(
        finding_id=p.finding.id, evaluation_id=unacceptable.id,
        decision_type=DecisionType.ACCEPT_DEVIATION,
        justification="structural test decision", decided_by=user.id,
        version_number=1))
    db.flush()

    assert finding_is_resolved(db, p.finding) is True
    assert derive_finding_status(db, p.finding) is FindingStatus.RESOLVED


def test_request_clarification_blocks_resolution(db, scenario):
    """Step 31 r10 — leaves the workflow unresolved until completed."""
    user, review, rv = scenario
    ev = _evidence(db, review)
    out = evaluate(numeric_input([cap(24, evidence=(ev.id,))]))   # APPROVAL_REQUIRED
    p = persist_evaluation(db, review=review, requirement_version_id=rv.id,
                           output=out)
    db.add(M.LegalDecision(
        finding_id=p.finding.id, evaluation_id=p.evaluations[0].id,
        decision_type=DecisionType.REQUEST_CLARIFICATION,
        justification="need more information", decided_by=user.id,
        version_number=1))
    db.flush()
    assert finding_is_resolved(db, p.finding) is False
    assert derive_finding_status(db, p.finding) is \
        FindingStatus.AWAITING_CLARIFICATION


def test_current_decision_is_the_highest_version(db, scenario):
    """N-1 Option C — current is derived from version_number, never a flag."""
    user, review, rv = scenario
    ev = _evidence(db, review)
    out = evaluate(numeric_input([cap(24, evidence=(ev.id,))]))
    p = persist_evaluation(db, review=review, requirement_version_id=rv.id,
                           output=out)
    evaluation = p.evaluations[0]
    for version, dtype in ((1, DecisionType.ACCEPT_DEVIATION),
                           (2, DecisionType.REJECT)):
        db.add(M.LegalDecision(
            finding_id=p.finding.id, evaluation_id=evaluation.id,
            decision_type=dtype, justification=f"v{version}",
            decided_by=user.id, version_number=version))
    db.flush()
    assert current_decision(db, evaluation.id).decision_type is DecisionType.REJECT


def test_decision_on_one_scope_does_not_dispose_of_another(db, scenario):
    """AB-1.1 — no Evaluation is implicitly disposed of by a decision on another."""
    user, review, rv = scenario
    e1, e2 = _evidence(db, review), _evidence(db, review)
    out = evaluate(numeric_input([
        cap(24, evidence=(e1.id,)),                                  # needs one
        cap(None, status="UNLIMITED", scope="SCOPE_B",
            kind=E.EvaluationKind.EXCEPTION, label="x",
            evidence=(e2.id,)),                                      # needs one
    ], rule=multi_scope_rule("SCOPE_B")))
    p = persist_evaluation(db, review=review, requirement_version_id=rv.id,
                           output=out)
    first = p.evaluations[0]
    db.add(M.LegalDecision(
        finding_id=p.finding.id, evaluation_id=first.id,
        decision_type=DecisionType.ACCEPT_DEVIATION, justification="one",
        decided_by=user.id, version_number=1))
    db.flush()
    assert finding_is_resolved(db, p.finding) is False   # the other still open
    assert current_decision(db, p.evaluations[1].id) is None


def test_an_unruled_deviation_reaches_DECISION_REQUIRED_end_to_end(db, scenario):
    """The policy verified through persistence, not through the predicate.

    `test_an_unruled_deviation_is_routed_to_a_human` asserts what the predicate
    returns. That is not the same claim: `derive_finding_status` consults the
    predicate, then looks for an existing decision, and the Finding status is what
    a Legal reviewer actually sees. This asserts the visible outcome against a real
    database, using the ratified 12-month standard and a real 24-month clause.

    Before the 2026-08-18 widening this Finding derived to OPEN.
    """
    user, review, rv = scenario
    ev = _evidence(db, review)
    # The ratified standard: 12 MONTHS of FEES_PAID (ToS 13). Structural scope and
    # unit names are reused so the shared `cap` helper applies; the assertion is
    # about routing, not about the vocabulary.
    ratified = structural_standard(preferred=12)
    out = evaluate(numeric_input(
        [cap(24, evidence=(ev.id,))], standard=ratified,
        rule=None))                       # rule=None: NO Legal Rule configured

    assert out.evaluations[0].classification is C.DEVIATION
    assert out.evaluations[0].rule_outcome is O.NOT_APPLICABLE   # no Legal Rule

    persisted = persist_evaluation(
        db, review=review, requirement_version_id=rv.id, output=out)
    assert persisted.finding.status is FindingStatus.DECISION_REQUIRED, (
        "an un-ruled deviation must be routed to a human, not left OPEN")


# ================================================== zero tolerance (2026-08-19)
def test_deviation_outcome_maps_any_deviation_to_the_configured_outcome():
    """The manager's zero-tolerance rule, wired: `deviation_outcome` disposes
    EVERY deviation identically, because the threshold keys cannot express it —
    `acceptable_max = preferred` would wrongly ACCEPT below-preferred values.
    Structural values; the policy mapping is what is under test."""
    from uuid import uuid4

    from legalmind.evaluation.contracts import LegalRule

    rule = LegalRule(version_id=uuid4(),
                     configuration={"deviation_outcome": "UNACCEPTABLE"},
                     rule_configuration={})
    for actual in (5, 24):          # below AND above preferred=10: both unacceptable
        out = evaluate(numeric_input([cap(actual)], rule=rule))
        ev = out.evaluations[0]
        assert ev.classification is C.DEVIATION
        assert ev.rule_outcome is O.UNACCEPTABLE
        assert evaluation_requires_decision(
            classification=ev.classification, rule_outcome=ev.rule_outcome,
            requirement_required=True) is True          # D-3.5(a): human decides

    # MATCH is untouched by the blanket rule: it never reaches the deviation map.
    out = evaluate(numeric_input([cap(10)], rule=rule))
    assert out.evaluations[0].classification is C.MATCH
    assert evaluation_requires_decision(
        classification=C.MATCH, rule_outcome=out.evaluations[0].rule_outcome,
        requirement_required=True) is False


def test_an_invalid_deviation_outcome_fails_closed_to_a_human():
    """Misconfiguration is never permission to guess (ENG-09): an unknown
    outcome value degrades to NOT_APPLICABLE, which still routes to Legal."""
    from uuid import uuid4

    from legalmind.evaluation.contracts import LegalRule
    rule = LegalRule(version_id=uuid4(),
                     configuration={"deviation_outcome": "REJECT_HARD"},
                     rule_configuration={})
    out = evaluate(numeric_input([cap(24)], rule=rule))
    ev = out.evaluations[0]
    assert ev.rule_outcome is O.NOT_APPLICABLE
    assert evaluation_requires_decision(
        classification=ev.classification, rule_outcome=ev.rule_outcome,
        requirement_required=True) is True
