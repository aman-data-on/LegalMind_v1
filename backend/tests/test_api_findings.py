"""The Finding / Evaluation surface — locked 49.7, LEGAL-02, AB-1, J-2, D-1.4.

Every test here defends one of 49.7's five normative rules, or LEGAL-02's
omission requirement. The rule that needs the most defending is r1: a Finding's
``classification`` is a **derived summary**, and returning it without its
Evaluations would present that summary as if it were authoritative.
"""

from __future__ import annotations

import pytest

from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.security import permissions as P
from legalmind.security.authorization import LEGAL_POSITION_FIELDS
from tests.conftest import (
    bespoke_role,
    grant,
    grant_role,
    make_evaluation,
    make_finding,
    make_review_for,
    make_user,
    sign_in,
)

V1 = "/api/v1"


@pytest.fixture
def owner(db, seeded):
    user = make_user(db)
    grant_role(db, user, P.ROLE_USER)
    return user


@pytest.fixture
def scoped(db, owner, requirement_version):
    """A Finding with two scoped Evaluations — the locked 45C shape: an
    AGGREGATE cap that conforms and a CATEGORY exception that does not."""
    review = make_review_for(db, owner)
    finding = make_finding(db, review, requirement_version,
                           classification=E.FindingClassification.DEVIATION)
    aggregate = make_evaluation(
        db, finding, scope_key="AGGREGATE",
        kind=E.EvaluationKind.PRIMARY,
        classification=E.FindingClassification.MATCH,
        rule_outcome=E.RuleOutcome.ACCEPTABLE)
    exception = make_evaluation(
        db, finding, scope_key="CATEGORY",
        kind=E.EvaluationKind.EXCEPTION,
        classification=E.FindingClassification.DEVIATION,
        rule_outcome=E.RuleOutcome.UNACCEPTABLE)
    exception.scope_label = "confidentiality breach"
    exception.expected_value = {"months": 6}
    exception.actual_value = {"months": 3}
    exception.operator = ">="
    exception.result = {"comparison": "3 < 6", "explanation": ["expected >= 6"],
                        "diagnostics": [], "evaluated_facts": {"caps": 2}}
    db.flush()
    return review, finding, aggregate, exception


def _legal_reviewer(db, review, owner):
    reviewer = make_user(db)
    grant_role(db, reviewer, P.ROLE_LEGAL_REVIEWER)
    db.add(M.ReviewAssignment(review_id=review.id, user_id=reviewer.id,
                              assigned_by=owner.id))
    db.flush()
    return reviewer


# =====================================================================
# 49.7 r1 — classification never travels without evaluations
# =====================================================================
def test_finding_response_nests_its_evaluations(api, db, owner, scoped):
    review, finding, aggregate, exception = scoped
    sign_in(api, db, owner)
    body = api.get(f"{V1}/findings/{finding.id}").json()["data"]

    assert body["classification"] == "DEVIATION"
    assert {e["scope_key"] for e in body["evaluations"]} == {"AGGREGATE", "CATEGORY"}
    # AB-1 / 45C — one Requirement, several scoped Evaluations, one Finding.
    assert len(body["evaluations"]) == 2
    assert body["evaluations"][1]["scope_label"] == "confidentiality breach"


def test_finding_list_items_also_nest_evaluations(api, db, owner, scoped):
    """r1 applies to a list as much as to a single resource: a summary presented
    alone is misleading wherever it appears."""
    review, finding, _, _ = scoped
    sign_in(api, db, owner)
    body = api.get(f"{V1}/reviews/{review.id}/findings").json()
    for item in body["data"]:
        assert "classification" in item
        assert item["evaluations"], "a classification was returned without them"


def test_no_response_carries_a_classification_without_evaluations(
        api, db, owner, scoped):
    """The structural version of r1: there is no serializer flag that could
    produce such a response, so this walks the real payloads."""
    review, finding, _, _ = scoped
    sign_in(api, db, owner)

    for path in (f"{V1}/findings/{finding.id}",
                 f"{V1}/reviews/{review.id}/findings"):
        payload = api.get(path).json()["data"]
        items = payload if isinstance(payload, list) else [payload]
        for item in items:
            if "evaluations" not in item and "classification" in item:
                # An Evaluation legitimately has a classification of its own; a
                # Finding-shaped object must not.
                assert "scope_key" in item


def test_finding_has_no_rule_outcome_field(api, db, owner, scoped):
    """49.7 r2 — no Finding-level ``rule_outcome`` exists, because none is
    persisted (J-2). Rule Outcome lives at Evaluation level only."""
    review, finding, _, _ = scoped
    reviewer = _legal_reviewer(db, review, owner)
    sign_in(api, db, reviewer)
    body = api.get(f"{V1}/findings/{finding.id}").json()["data"]

    assert "rule_outcome" not in body
    # ...and it IS present on each Evaluation, for a caller permitted to see it.
    assert all("rule_outcome" in e for e in body["evaluations"])


def test_requires_decision_is_derived_not_stored(api, db, owner, scoped):
    """49.7 r2 — derived. The UNACCEPTABLE exception requires a decision
    (D-3.5 a) while the ACCEPTABLE aggregate does not."""
    review, finding, _, _ = scoped
    sign_in(api, db, owner)
    body = api.get(f"{V1}/findings/{finding.id}").json()["data"]
    by_scope = {e["scope_key"]: e for e in body["evaluations"]}
    assert by_scope["CATEGORY"]["requires_decision"] is True
    assert by_scope["AGGREGATE"]["requires_decision"] is False
    assert body["requires_decision"] is True


# =====================================================================
# 49.7 r3 — evidence_refs is always an array, and may be empty
# =====================================================================
def test_evidence_refs_is_an_empty_array_never_null(api, db, owner,
                                                    requirement_version):
    """A MISSING arising from established absence legitimately carries zero
    evidence (45D.4.10, N-34). It must never be ``null``, and synthetic evidence
    must never be created to avoid the empty case (45C.25)."""
    review = make_review_for(db, owner)
    finding = make_finding(db, review, requirement_version,
                           classification=E.FindingClassification.MISSING)
    make_evaluation(db, finding,
                    classification=E.FindingClassification.MISSING,
                    rule_outcome=E.RuleOutcome.UNACCEPTABLE)

    sign_in(api, db, owner)
    body = api.get(f"{V1}/findings/{finding.id}").json()["data"]
    refs = body["evaluations"][0]["evidence_refs"]
    assert refs == []
    assert refs is not None
    assert body["evidence"] == []


# =====================================================================
# LEGAL-02 / 49.7 r4 — omitted, not nulled
# =====================================================================
def test_legal_position_is_omitted_for_a_caller_without_the_permission(
        api, db, owner, scoped):
    """A null would still signal that a value exists (Step 52.4). The normal-user
    and authorized-legal views are structurally different views, not the same
    view with fields masked."""
    review, finding, _, _ = scoped
    sign_in(api, db, owner)
    assert P.LEGAL_POSITION_VIEW not in \
        api.get(f"{V1}/auth/session").json()["data"]["permissions"]

    body = api.get(f"{V1}/findings/{finding.id}").json()["data"]
    for evaluation in body["evaluations"]:
        for field in LEGAL_POSITION_FIELDS:
            assert field not in evaluation, field
        # What remains is the counterparty's own contract plus the fact that
        # authorized review is needed — neither is an internal legal position.
        assert "classification" in evaluation
        assert "actual_value" in evaluation
        assert "requires_decision" in evaluation


def test_no_threshold_leaks_in_the_serialized_payload(api, db, owner, scoped):
    """49.5 r2 / LEGAL-02 — no thresholds anywhere in the response, including
    inside the explanation text, which reconstructs the Standard and the Rule."""
    review, finding, _, _ = scoped
    sign_in(api, db, owner)
    raw = api.get(f"{V1}/findings/{finding.id}").text
    assert "expected >= 6" not in raw
    assert "3 < 6" not in raw
    assert "UNACCEPTABLE" not in raw


def test_legal_reviewer_sees_the_full_position(api, db, owner, scoped):
    """Rule 12's explainability, satisfied for the audience internal legal
    positions are for: every holder of ``legal_position.view``."""
    review, finding, _, _ = scoped
    reviewer = _legal_reviewer(db, review, owner)
    sign_in(api, db, reviewer)
    body = api.get(f"{V1}/findings/{finding.id}").json()["data"]
    exception = [e for e in body["evaluations"] if e["scope_key"] == "CATEGORY"][0]

    assert exception["rule_outcome"] == "UNACCEPTABLE"
    assert exception["expected_value"] == {"months": 6}
    assert exception["operator"] == ">="
    assert exception["explanation"] == ["expected >= 6"]


def test_evaluations_endpoint_applies_the_same_gate(api, db, owner, scoped):
    """A second route to the same data must not be a second disclosure
    posture."""
    review, finding, _, _ = scoped
    sign_in(api, db, owner)
    for evaluation in api.get(
            f"{V1}/findings/{finding.id}/evaluations").json()["data"]:
        assert "rule_outcome" not in evaluation

    reviewer = _legal_reviewer(db, review, owner)
    sign_in(api, db, reviewer)
    for evaluation in api.get(
            f"{V1}/findings/{finding.id}/evaluations").json()["data"]:
        assert "rule_outcome" in evaluation


def test_evaluation_view_is_a_distinct_permission(api, db, owner, scoped):
    """49.3 gates ``/findings/{id}/evaluations`` on ``evaluation.view``, not on
    ``finding.view``."""
    review, finding, _, _ = scoped
    narrow = make_user(db)
    grant(db, narrow, bespoke_role(db, "FINDINGS_ONLY",
                                   [P.REVIEW_VIEW, P.FINDING_VIEW]))
    db.add(M.ReviewAssignment(review_id=review.id, user_id=narrow.id,
                              assigned_by=owner.id))
    db.flush()

    sign_in(api, db, narrow)
    assert api.get(f"{V1}/findings/{finding.id}").status_code == 200
    assert api.get(f"{V1}/findings/{finding.id}/evaluations").status_code == 403


# =====================================================================
# 47.9 / Step 24 r8 — the audit projection
# =====================================================================
def test_audit_state_payloads_are_gated(api, db, owner, scoped):
    """Locked Step 24 r8 — a Super Admin holds ``audit.view`` but no
    ``legal_position.view``, and "does not automatically have access to
    confidential contract or Legal content". The envelope is returned; the
    payload is omitted, not nulled."""
    from legalmind.security import audit as A

    review, finding, _, exception = scoped
    A.record(db, action=A.LEGAL_DECISION_RECORDED, entity_type="evaluation",
             entity_id=exception.id, actor_id=owner.id,
             after={"decision_type": "ACCEPT_DEVIATION"})

    admin = make_user(db)
    grant_role(db, admin, P.ROLE_SUPER_ADMIN)
    sign_in(api, db, admin)
    body = api.get(f"{V1}/audit-events").json()
    assert body["data"]
    for event in body["data"]:
        assert "action" in event and "entity_type" in event
        assert "after_state" not in event
        assert "before_state" not in event
    assert "ACCEPT_DEVIATION" not in api.get(f"{V1}/audit-events").text
