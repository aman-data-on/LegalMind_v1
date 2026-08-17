"""Decisions, escalation and lifecycle over HTTP — locked 49.7, 49.8, Steps 4,
30, 31, AB-1.1, AM-12, AM-15, D-3.5, D-3.6.

Several of these assert the *absence* of a route. That is deliberate: locked
Step 31 r14 makes supersession a create, AB-1.1 forbids a Finding-level decision,
and D-3.6 makes resolution derived — each of which is a route that must not exist,
and none of which any positive test would catch.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from legalmind.api.permission_map import ENDPOINT_PERMISSIONS
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.security import permissions as P
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
def case(db, owner, requirement_version):
    """A Review in LEGAL_REVIEW with one Evaluation that requires a decision."""
    review = make_review_for(db, owner)
    review.status = E.ReviewStatus.LEGAL_REVIEW
    finding = make_finding(db, review, requirement_version)
    evaluation = make_evaluation(
        db, finding, classification=E.FindingClassification.DEVIATION,
        rule_outcome=E.RuleOutcome.APPROVAL_REQUIRED)
    db.flush()
    return review, finding, evaluation


def decider(db, review, owner, *, name="D"):
    user = make_user(db)
    grant_role(db, user, P.ROLE_LEGAL_REVIEWER)
    grant(db, user, bespoke_role(db, f"AUTH_{name}_{user.id.hex[:6]}",
                                 [P.LEGAL_DECISION, P.LEGAL_APPROVE_CUSTOMIZATION]))
    db.add(M.ReviewAssignment(review_id=review.id, user_id=user.id,
                              assigned_by=owner.id))
    db.flush()
    return user


# =====================================================================
# Routes that must not exist
# =====================================================================
def test_there_is_no_finding_level_decision_endpoint():
    """AB-1.1 — a decision resolves exactly ONE Evaluation and must never
    implicitly dispose of another under the same Finding."""
    assert not any(path.endswith("/decisions") and "findings" in path
                   for _, path in ENDPOINT_PERMISSIONS)


def test_there_is_no_decision_update_endpoint():
    """Step 31 r14 / 49.7 — supersession is a create. An update endpoint would
    make history rewritable at the API even though the trigger forbids it."""
    decision_routes = {(method, path) for method, path in ENDPOINT_PERMISSIONS
                       if path.endswith("/decisions")}
    assert {method for method, _ in decision_routes} == {"POST", "GET"}


def test_there_is_no_endpoint_that_sets_review_or_finding_status():
    """Step 30 r3 — users cannot arbitrarily set Review status; D-3.6 — a Finding
    is resolved by derivation, never by assertion."""
    for _, path in ENDPOINT_PERMISSIONS:
        assert not path.endswith("/status")
        assert not path.endswith("/resolve")


def test_decisions_are_recorded_against_an_evaluation_not_a_finding(api, db,
                                                                    owner, case):
    review, finding, evaluation = case
    sign_in(api, db, decider(db, review, owner))
    response = api.post(f"{V1}/evaluations/{evaluation.id}/decisions",
                        json={"decision_type": "ACCEPT_DEVIATION",
                              "justification": "within the agreed tolerance"})
    assert response.status_code == 201
    assert response.json()["data"]["decision"]["evaluation_id"] == str(evaluation.id)
    # 404, not 405: the path does not exist and existence is not disclosed.
    assert api.post(f"{V1}/findings/{finding.id}/decisions",
                    json={}).status_code == 404


# =====================================================================
# 49.7 / AM-12 / N-1 Option C — versioning
# =====================================================================
def test_supersession_appends_a_version_and_keeps_the_first(api, db, owner, case):
    review, finding, evaluation = case
    sign_in(api, db, decider(db, review, owner))

    first = api.post(f"{V1}/evaluations/{evaluation.id}/decisions",
                     json={"decision_type": "REQUEST_CLARIFICATION",
                           "justification": "please supply the schedule"})
    assert first.json()["data"]["decision"]["version_number"] == 1

    second = api.post(f"{V1}/evaluations/{evaluation.id}/decisions",
                      json={"decision_type": "ACCEPT_DEVIATION",
                            "justification": "schedule received; acceptable",
                            "expected_version": 1})
    assert second.json()["data"]["decision"]["version_number"] == 2

    chain = api.get(f"{V1}/evaluations/{evaluation.id}/decisions").json()["data"]
    assert [d["version_number"] for d in chain] == [1, 2]
    assert [d["is_current"] for d in chain] == [False, True]
    # r14 — the superseded row is returned unchanged, never rewritten.
    assert chain[0]["decision_type"] == "REQUEST_CLARIFICATION"


def test_stale_expected_version_is_409(api, db, owner, case):
    """49.7 — optimistic concurrency falls out of
    ``UNIQUE(evaluation_id, version_number)`` with no separate ETag mechanism."""
    review, finding, evaluation = case
    sign_in(api, db, decider(db, review, owner))

    api.post(f"{V1}/evaluations/{evaluation.id}/decisions",
             json={"decision_type": "ACCEPT_DEVIATION", "justification": "first"})
    conflict = api.post(f"{V1}/evaluations/{evaluation.id}/decisions",
                        json={"decision_type": "REJECT", "justification": "second",
                              "expected_version": 0})
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "DECISION_VERSION_CONFLICT"


def test_a_duplicate_submission_fails_loudly(api, db, owner, case):
    """49.8 — decision creation is deliberately not idempotent by key. It is
    versioned instead, so a duplicate submission is a 409: a legal decision
    should fail loudly rather than appear to have succeeded twice."""
    review, finding, evaluation = case
    sign_in(api, db, decider(db, review, owner))
    body = {"decision_type": "ACCEPT_DEVIATION", "justification": "agreed",
            "expected_version": 0}
    assert api.post(f"{V1}/evaluations/{evaluation.id}/decisions",
                    json=body).status_code == 201
    assert api.post(f"{V1}/evaluations/{evaluation.id}/decisions",
                    json=body).status_code == 409


def test_justification_is_mandatory(api, db, owner, case):
    """Step 31 r11 / AM-15. Whitespace is rejected too, which the NOT NULL column
    alone cannot do."""
    review, finding, evaluation = case
    sign_in(api, db, decider(db, review, owner))
    assert api.post(f"{V1}/evaluations/{evaluation.id}/decisions",
                    json={"decision_type": "REJECT"}).status_code == 422
    assert api.post(f"{V1}/evaluations/{evaluation.id}/decisions",
                    json={"decision_type": "REJECT",
                          "justification": "   "}).status_code == 403


def test_reading_the_chain_needs_only_finding_view(api, db, owner, case):
    """49.3 gates the GET on ``finding.view``: reading what was decided is not
    the same authority as deciding."""
    review, finding, evaluation = case
    sign_in(api, db, decider(db, review, owner))
    api.post(f"{V1}/evaluations/{evaluation.id}/decisions",
             json={"decision_type": "ACCEPT_DEVIATION", "justification": "ok"})

    sign_in(api, db, owner)
    read = api.get(f"{V1}/evaluations/{evaluation.id}/decisions")
    assert read.status_code == 200
    assert len(read.json()["data"]) == 1
    # ...and the owner still cannot decide.
    assert api.post(f"{V1}/evaluations/{evaluation.id}/decisions",
                    json={"decision_type": "REJECT",
                          "justification": "changed my mind"}).status_code == 403


# =====================================================================
# Step 31 r10 / r15 — effectiveness
# =====================================================================
def test_request_clarification_is_never_effective(api, db, owner, case):
    """Step 31 r10 — it leaves the workflow unresolved until completed."""
    review, finding, evaluation = case
    sign_in(api, db, decider(db, review, owner))
    body = api.post(f"{V1}/evaluations/{evaluation.id}/decisions",
                    json={"decision_type": "REQUEST_CLARIFICATION",
                          "justification": "need the schedule"}).json()["data"]
    assert body["is_effective"] is False
    assert body["finding_status"] == "AWAITING_CLARIFICATION"
    assert body["review_status"] == "LEGAL_REVIEW"


def test_second_person_approval_needs_a_different_actor(api, db, owner, case):
    """Step 31 r15 / F-2 — co-signature within the append-only chain. The same
    person repeating themselves does not count, and a disagreeing second actor
    does not confirm."""
    review, finding, evaluation = case
    first = decider(db, review, owner, name="A")
    second = decider(db, review, owner, name="B")

    sign_in(api, db, first)
    one = api.post(f"{V1}/evaluations/{evaluation.id}/decisions",
                   json={"decision_type": "ACCEPT_DEVIATION",
                         "justification": "acceptable",
                         "requires_second_person": True}).json()["data"]
    assert one["is_effective"] is False

    same_again = api.post(f"{V1}/evaluations/{evaluation.id}/decisions",
                          json={"decision_type": "ACCEPT_DEVIATION",
                                "justification": "still acceptable",
                                "requires_second_person": True}).json()["data"]
    assert same_again["is_effective"] is False

    sign_in(api, db, second)
    co_signed = api.post(f"{V1}/evaluations/{evaluation.id}/decisions",
                         json={"decision_type": "ACCEPT_DEVIATION",
                               "justification": "independently reviewed; agreed",
                               "requires_second_person": True}).json()["data"]
    assert co_signed["is_effective"] is True


# =====================================================================
# Step 30 r7 / r16 — RESOLVED is derived
# =====================================================================
def test_review_advances_to_resolved_only_when_nothing_is_outstanding(
        api, db, owner, requirement_version):
    review = make_review_for(db, owner)
    review.status = E.ReviewStatus.LEGAL_REVIEW
    first = make_finding(db, review, requirement_version)
    first_evaluation = make_evaluation(
        db, first, rule_outcome=E.RuleOutcome.APPROVAL_REQUIRED)

    other_requirement = M.Requirement(code=f"R-{review.id.hex[:6]}",
                                      status=E.ConfigStatus.ACTIVE)
    db.add(other_requirement); db.flush()
    other_version = M.RequirementVersion(
        requirement_id=other_requirement.id, version_number=1, name="Other",
        evaluator_type=E.EvaluatorType.PRESENCE, created_by=owner.id)
    db.add(other_version); db.flush()
    second = make_finding(db, review, other_version)
    second_evaluation = make_evaluation(
        db, second, rule_outcome=E.RuleOutcome.UNACCEPTABLE)

    sign_in(api, db, decider(db, review, owner))

    partial = api.post(f"{V1}/evaluations/{first_evaluation.id}/decisions",
                       json={"decision_type": "ACCEPT_DEVIATION",
                             "justification": "ok"})
    assert partial.status_code == 201
    # One Finding still outstanding, so the Review must stay in LEGAL_REVIEW.
    assert partial.json()["data"]["review_status"] == "LEGAL_REVIEW"

    final = api.post(f"{V1}/evaluations/{second_evaluation.id}/decisions",
                     json={"decision_type": "REQUIRE_COMPANY_STANDARD",
                           "justification": "revert to our standard wording"})
    assert final.json()["data"]["review_status"] == "RESOLVED"


def test_resolved_does_not_change_the_finding_classification(api, db, owner, case):
    """Locked Step 30 r8 and rule 14 — RESOLVED != MATCH. A resolved workflow
    state must never be recorded as a MATCH."""
    review, finding, evaluation = case
    sign_in(api, db, decider(db, review, owner))
    api.post(f"{V1}/evaluations/{evaluation.id}/decisions",
             json={"decision_type": "ACCEPT_DEVIATION",
                   "justification": "accepted"})

    body = api.get(f"{V1}/findings/{finding.id}").json()["data"]
    assert body["status"] == "RESOLVED"
    assert body["classification"] == "DEVIATION"


# =====================================================================
# Steps 4 / 22 / D-3.5 d — escalation
# =====================================================================
def test_an_ordinary_user_may_escalate(api, db, owner, requirement_version):
    """Locked ROLE-03 — a User can compare, view and escalate, but never decide.
    49.3 gates escalation on ``review.view`` for exactly that reason."""
    review = make_review_for(db, owner)
    finding = make_finding(db, review, requirement_version,
                           classification=E.FindingClassification.MATCH,
                           status=E.FindingStatus.OPEN)
    make_evaluation(db, finding, classification=E.FindingClassification.MATCH,
                    rule_outcome=E.RuleOutcome.ACCEPTABLE)

    sign_in(api, db, owner)
    response = api.post(f"{V1}/findings/{finding.id}/escalate",
                        json={"reason": "unsure this matches our standard"})
    assert response.status_code == 201
    body = response.json()["data"]
    assert body["finding"]["escalated"] is True
    # D-3.5 d — escalation makes even a MATCH require a decision...
    assert body["finding"]["status"] == "DECISION_REQUIRED"
    # ...without disposing of anything. Step 4: escalation is not approval.
    assert db.execute(select(M.LegalDecision)).first() is None
    assert body["finding"]["classification"] == "MATCH"


def test_escalation_is_idempotent(api, db, owner, requirement_version):
    review = make_review_for(db, owner)
    finding = make_finding(db, review, requirement_version)
    make_evaluation(db, finding, rule_outcome=E.RuleOutcome.ACCEPTABLE)

    sign_in(api, db, owner)
    first = api.post(f"{V1}/findings/{finding.id}/escalate",
                     json={"reason": "please review"})
    second = api.post(f"{V1}/findings/{finding.id}/escalate",
                      json={"reason": "please review again"})
    assert (first.json()["data"]["escalation"]["id"]
            == second.json()["data"]["escalation"]["id"])
    assert db.execute(select(M.Escalation)).scalars().all().__len__() == 1


def test_withdrawing_an_escalation_reverses_the_requirement(
        api, db, owner, requirement_version):
    review = make_review_for(db, owner)
    finding = make_finding(db, review, requirement_version,
                           classification=E.FindingClassification.MATCH)
    make_evaluation(db, finding, classification=E.FindingClassification.MATCH,
                    rule_outcome=E.RuleOutcome.ACCEPTABLE)

    sign_in(api, db, owner)
    api.post(f"{V1}/findings/{finding.id}/escalate", json={"reason": "check"})
    withdrawn = api.delete(f"{V1}/findings/{finding.id}/escalate").json()["data"]
    assert withdrawn["escalated"] is False
    assert withdrawn["status"] == "OPEN"
    # AUD-01 — the escalation happened; the record is marked, never deleted.
    escalation = db.execute(select(M.Escalation)).scalars().one()
    assert escalation.withdrawn_at is not None


def test_escalating_does_not_require_legal_authority(api, db, owner,
                                                     requirement_version):
    review = make_review_for(db, owner)
    finding = make_finding(db, review, requirement_version)
    make_evaluation(db, finding, rule_outcome=E.RuleOutcome.ACCEPTABLE)

    sign_in(api, db, owner)
    assert P.LEGAL_DECISION not in \
        api.get(f"{V1}/auth/session").json()["data"]["permissions"]
    assert api.post(f"{V1}/findings/{finding.id}/escalate",
                    json={"reason": "review please"}).status_code == 201


def test_every_decision_is_audited_with_the_request_id(api, db, owner, case):
    """Step 31 r19 / SEC-09 / 49.9."""
    review, finding, evaluation = case
    sign_in(api, db, decider(db, review, owner))
    api.post(f"{V1}/evaluations/{evaluation.id}/decisions",
             json={"decision_type": "ACCEPT_DEVIATION", "justification": "ok"},
             headers={"X-Request-Id": "decision-trace-1"})

    event = db.execute(
        select(M.AuditEvent)
        .where(M.AuditEvent.action == "legal.decision_recorded")
    ).scalars().one()
    assert event.entity_id == evaluation.id
    assert event.event_metadata["request_id"] == "decision-trace-1"
