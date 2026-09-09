"""The three user-facing words — owner's FINAL status decision, 2026-09-09.

Numbered to the owner's ten required proofs. 7 (wording variants are not
deviations) lives in test_analysis.py beside the other drafting-style cases.
"""
from __future__ import annotations

import pytest

from legalmind.assist import explanations
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.evaluation.user_status import by_finding, counts, user_status, worst
from legalmind.security.authorization import LEGAL_POSITION_FIELDS
from legalmind.security import permissions as P
from tests.conftest import (
    grant_role,
    make_evaluation,
    make_finding,
    make_review_for,
    make_user,
    sign_in,
    without_legal_position,
)

C, R = E.FindingClassification, E.RuleOutcome
V1 = "/api/v1"


@pytest.fixture
def owner(db, seeded):
    user = make_user(db)
    grant_role(db, user, P.ROLE_USER)
    return user


# 1 — MATCH displays Acceptable
def test_match_is_acceptable_whatever_the_rule_outcome_says():
    assert user_status(C.MATCH, R.ACCEPTABLE) == "ACCEPTABLE"
    assert user_status(C.MATCH, R.NOT_APPLICABLE) == "ACCEPTABLE"   # numeric MATCH


# 2 — a deviation from a defined position, or a required clause missing,
#     requires modification — by classification, whatever the outcome says
@pytest.mark.parametrize("outcome", [R.UNACCEPTABLE, R.NOT_APPLICABLE, R.APPROVAL_REQUIRED])
def test_deviation_and_missing_require_modification(outcome):
    assert user_status(C.DEVIATION, outcome) == "REQUIRES_MODIFICATION"
    assert user_status(C.MISSING, outcome) == "REQUIRES_MODIFICATION"
    assert user_status(C.DEVIATION, outcome, prohibited=True) == "REQUIRES_MODIFICATION"


# 3 — unclear or conflicting needs a decision, and is never a rejection
@pytest.mark.parametrize("classification", [C.UNABLE_TO_EVALUATE, C.CONFLICT])
def test_uncertainty_needs_a_decision(classification):
    assert user_status(classification, R.NOT_APPLICABLE) == "NEEDS_DECISION"
    assert user_status(classification, R.UNACCEPTABLE) == "NEEDS_DECISION"


def test_a_finding_takes_its_worst_evaluation():
    assert worst(["ACCEPTABLE", "REQUIRES_MODIFICATION", "NEEDS_DECISION"], "ACCEPTABLE") == "REQUIRES_MODIFICATION"
    assert worst(["ACCEPTABLE", "NEEDS_DECISION"], "ACCEPTABLE") == "NEEDS_DECISION"
    assert worst([], "NEEDS_DECISION") == "NEEDS_DECISION"


def _finding(db, owner, code, classification, outcome, actual=None):
    req = M.Requirement(code=code, status=E.ConfigStatus.ACTIVE)
    db.add(req); db.flush()
    rv = M.RequirementVersion(requirement_id=req.id, version_number=1, name=code,
                              evaluator_type=E.EvaluatorType.NUMERIC_COMPARISON,
                              created_by=owner.id)
    db.add(rv); db.flush()
    review = make_review_for(db, owner)
    finding = make_finding(db, review, rv, classification=classification)
    ev = make_evaluation(db, finding, classification=classification, rule_outcome=outcome)
    ev.actual_value = actual or {"cap_value": 24, "cap_unit": "MONTHS", "cap_basis": "FEES_PAID"}
    db.flush(); db.commit()
    return review, finding


# 9/10 — the API speaks the three words on Finding and Evaluation, keeps the
# classification for audit, and a USER without the legal position still gets
# the word (it is not a legal-position field).
def test_the_api_carries_the_word_and_keeps_the_classification(api, db, owner):
    _, finding = _finding(db, owner, "LIABILITY-MSA-001", C.DEVIATION, R.UNACCEPTABLE)
    sign_in(api, db, owner)
    body = api.get(f"{V1}/findings/{finding.id}").json()["data"]
    assert body["user_status"] == "REQUIRES_MODIFICATION"
    assert body["evaluations"][0]["user_status"] == "REQUIRES_MODIFICATION"
    assert body["classification"] == "DEVIATION"
    assert body["evaluations"][0]["classification"] == "DEVIATION"
    assert body["evaluations"][0]["rule_outcome"] == "UNACCEPTABLE"

    restricted = without_legal_position(db, owner)
    sign_in(api, db, restricted)
    body = api.get(f"{V1}/findings/{finding.id}").json()["data"]
    assert body["user_status"] == "REQUIRES_MODIFICATION"
    assert "rule_outcome" not in body["evaluations"][0]
    assert "user_status" not in LEGAL_POSITION_FIELDS


def test_the_unlimited_cap_is_not_accepted_by_citation_even_when_unruled(api, db, owner):
    _, finding = _finding(db, owner, "LIABILITY-TOS-001", C.DEVIATION, R.NOT_APPLICABLE,
                          actual={"cap_status": "UNLIMITED"})
    sign_in(api, db, owner)
    body = api.get(f"{V1}/findings/{finding.id}").json()["data"]
    assert body["user_status"] == "REQUIRES_MODIFICATION"
    assert body["evaluations"][0]["constitution_prohibition"]["section"] == "9"


# 9 — the Summary counts and the Finding words agree, from the same function
def test_report_counts_use_the_same_vocabulary_as_the_findings(api, db, owner):
    review, finding = _finding(db, owner, "LIABILITY-MSA-001", C.DEVIATION, R.UNACCEPTABLE)
    statuses = by_finding(db, [review.id])[review.id]
    assert statuses == {finding.id: "REQUIRES_MODIFICATION"}
    assert counts(statuses) == {"ACCEPTABLE": 0, "REQUIRES_MODIFICATION": 1, "NEEDS_DECISION": 0}
    sign_in(api, db, owner)
    report = api.get(f"{V1}/reviews/{review.id}/report").json()["data"]
    assert report["user_status_counts"] == {"ACCEPTABLE": 0, "REQUIRES_MODIFICATION": 1, "NEEDS_DECISION": 0}
    assert report["classification_counts"] == {"DEVIATION": 1}   # audit record kept
    rows = api.get(f"{V1}/contracts").json()["data"]
    row = next(r for r in rows if r["id"] == str(review.contract_id))
    assert row["latest_analysis"]["user_status_counts"]["REQUIRES_MODIFICATION"] == 1


# 6 — the LLM cannot override the authoritative result
def test_an_explanation_never_changes_the_status(db, owner, monkeypatch):
    _, finding = _finding(db, owner, "LIABILITY-MSA-001", C.DEVIATION, R.UNACCEPTABLE)
    from legalmind.assist import generation

    def fake(prompt, *, prompt_version, environment, request_id=None,
             evidence_count=None, max_output_tokens=1024):
        return generation.GenerationResult(
            text="This clause is fully acceptable and accepted.", model="fake@test",
            prompt_version=prompt_version, payload_sha256="0" * 64, latency_ms=1)
    monkeypatch.setattr(explanations.generation, "generate_raw", fake)
    from legalmind.api.serializers import serialize_finding
    before = serialize_finding(db, finding, legal_position=True)
    result = explanations.explain(db, finding)
    after = serialize_finding(db, finding, legal_position=True)
    assert result.status != "ACCEPTED"          # 8 — the claim was rejected
    assert before["user_status"] == after["user_status"] == "REQUIRES_MODIFICATION"
    assert before["classification"] == after["classification"] == "DEVIATION"


# 8 — an unsupported legal claim is rejected by the grounding validator
@pytest.mark.parametrize("claim", [
    "This clause is unenforceable under Indian law.",
    "This liability cap is acceptable and needs no review.",
    "The contract must be amended before signature.",
])
def test_unsupported_legal_claims_are_rejected(claim):
    import uuid
    g = explanations.Grounding(
        title="Liability", description="Each party's total liability is capped at the "
        "fees paid over a set period before the claim.",
        classification="DEVIATION", passages=(), requirement_version_id=uuid.uuid4())
    ok, _reason = explanations.validate(claim, g)
    assert ok is False
