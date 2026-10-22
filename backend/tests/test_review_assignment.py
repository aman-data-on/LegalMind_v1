"""Send for review (AB-100, owner 2026-10-21): the contract's owner sends its Review to one
designated reviewer, who decides; the owner never decides their own points (SEC-01); every
step is audited, the reason included; anyone out of scope gets the one 404 (SEC-07)."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.security import audit as A
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
    review = make_review_for(db, owner)
    review.status = E.ReviewStatus.LEGAL_REVIEW
    finding = make_finding(db, review, requirement_version)
    evaluation = make_evaluation(db, finding,
                                 classification=E.FindingClassification.DEVIATION,
                                 rule_outcome=E.RuleOutcome.UNACCEPTABLE)
    db.flush()
    return review, evaluation


def _reviewer(db, name="R"):
    """A designated reviewer: Legal Reviewer + a legal.decision grant (S-8 bootstraps
    the first one; here the fixture grants it directly)."""
    user = make_user(db)
    grant_role(db, user, P.ROLE_LEGAL_REVIEWER)
    grant(db, user, bespoke_role(db, f"AUTH_{name}_{user.id.hex[:6]}", [P.LEGAL_DECISION]))
    db.flush()
    return user


def _send(api, review, user):
    return api.post(f"{V1}/reviews/{review.id}/assignments", json={"user_id": str(user.id)})


def test_the_owner_sees_eligible_reviewers_and_sends_the_review(api, db, owner, case):
    review, _ = case
    reviewer, plain = _reviewer(db), make_user(db)
    grant_role(db, plain, P.ROLE_USER)
    sign_in(api, db, owner)
    listed = api.get(f"{V1}/reviews/{review.id}/assignments").json()["data"]
    emails = {r["email"] for r in listed["eligible"]}
    assert listed["can_send"] is True
    assert reviewer.email in emails and plain.email not in emails
    sent = _send(api, review, reviewer)
    assert sent.status_code == 201
    assert [a["email"] for a in sent.json()["data"]["assigned"]] == [reviewer.email]
    event = db.execute(select(M.AuditEvent).where(
        M.AuditEvent.action == A.REVIEW_ASSIGNED)).scalars().one()
    assert (event.actor_id, event.after_state["assigned_to"]) == (owner.id, str(reviewer.id))


def test_the_reviewer_reads_the_contract_and_decides_with_the_reason_audited(api, db,
                                                                             owner, case):
    review, evaluation = case
    reviewer = _reviewer(db)
    sign_in(api, db, owner)
    _send(api, review, reviewer)
    sign_in(api, db, reviewer)
    assert api.get(f"{V1}/contracts/{review.contract_id}").status_code == 200
    seen = api.get(f"{V1}/reviews/{review.id}/assignments").json()["data"]
    assert (seen["can_send"], seen["eligible"]) == (False, [])      # only the owner sends
    decided = api.post(f"{V1}/evaluations/{evaluation.id}/decisions",
                       json={"decision_type": "ACCEPT_DEVIATION",
                             "justification": "small deal; accepted as an exception"})
    assert decided.status_code == 201
    event = db.execute(select(M.AuditEvent).where(
        M.AuditEvent.action == A.LEGAL_DECISION_RECORDED)).scalars().one()
    assert event.after_state["justification"] == "small deal; accepted as an exception"
    assert event.actor_id == reviewer.id


def test_only_a_person_holding_both_legal_roles_can_be_sent_it(api, db, owner, case):
    review, _ = case
    plain = make_user(db)
    grant_role(db, plain, P.ROLE_LEGAL_REVIEWER)        # review, but no legal.decision
    sign_in(api, db, owner)
    assert _send(api, review, plain).status_code == 422


def test_the_owner_never_decides_their_own_points(api, db, owner, case):
    review, evaluation = case
    grant(db, owner, bespoke_role(db, "OWNER_DEC", [P.LEGAL_REVIEW, P.LEGAL_DECISION]))
    sign_in(api, db, owner)
    assert _send(api, review, owner).status_code == 422


def test_someone_else_cannot_send_or_see_it(api, db, owner, case):
    review, _ = case
    reviewer, stranger = _reviewer(db), make_user(db)
    grant_role(db, stranger, P.ROLE_USER)
    sign_in(api, db, stranger)
    assert _send(api, review, reviewer).status_code == 404
    assert api.get(f"{V1}/reviews/{review.id}/assignments").status_code == 404


def test_withdrawing_ends_the_reviewers_access_and_is_audited(api, db, owner, case):
    """Outside REC-09's Legal scope the assignment is the reviewer's only way in."""
    review, _ = case
    review.status = E.ReviewStatus.ANALYSIS_COMPLETE
    db.flush()
    reviewer = _reviewer(db)
    sign_in(api, db, owner)
    _send(api, review, reviewer)
    assert _send(api, review, reviewer).status_code == 409       # already with them
    out = api.delete(f"{V1}/reviews/{review.id}/assignments/{reviewer.id}")
    assert out.status_code == 200 and out.json()["data"]["assigned"] == []
    assert db.execute(select(M.AuditEvent).where(
        M.AuditEvent.action == A.REVIEW_ASSIGNMENT_WITHDRAWN)).scalars().one()
    sign_in(api, db, reviewer)
    assert api.get(f"{V1}/reviews/{review.id}").status_code == 404
    sign_in(api, db, owner)
    assert _send(api, review, reviewer).status_code == 201       # sent again


def test_a_person_the_review_was_sent_to_sees_only_that_review(api, db, owner, case):
    review, _ = case
    other = make_review_for(db, owner)
    reviewer = _reviewer(db)
    sign_in(api, db, owner)
    _send(api, review, reviewer)
    sign_in(api, db, reviewer)
    assert api.get(f"{V1}/reviews/{other.id}").status_code == 404


def test_rec_09_still_shows_every_legal_reviewer_a_review_awaiting_a_decision(api, db,
                                                                          owner, case):
    """Locked REC-09, unchanged by AB-100: a review in LEGAL_REVIEW is in Legal scope for
    every `legal.review` holder, sent to them or not. Owner decision pending."""
    review, _ = case
    sign_in(api, db, _reviewer(db, "OTHER"))
    assert api.get(f"{V1}/reviews/{review.id}").status_code == 200


def test_the_first_reviewer_is_granted_once_by_an_audited_bootstrap(db, seeded):
    from tools.grant_legal_authority import grant_first
    person = make_user(db)
    assert set(grant_first(db, person.email, "test operator")) == {
        P.ROLE_LEGAL_REVIEWER, P.ROLE_LEGAL_DECISION_AUTHORITY}
    events = db.execute(select(M.AuditEvent).where(
        M.AuditEvent.action == A.ADMIN_LEGAL_AUTHORITY_GRANTED)).scalars().all()
    assert {e.after_state["operator"] for e in events} == {"test operator"}
    with pytest.raises(SystemExit, match=r"already holds legal\.decision"):
        grant_first(db, make_user(db).email, "test operator")      # S-8 from now on


def test_the_reviews_list_marks_what_was_sent_to_you(api, db, owner, case):
    review, _ = case
    reviewer = _reviewer(db)
    sign_in(api, db, owner)
    _send(api, review, reviewer)
    sign_in(api, db, reviewer)
    rows = api.get(f"{V1}/reviews").json()["data"]
    assert [r["sent_to_you"] for r in rows if r["id"] == str(review.id)] == [True]


def test_a_later_grant_is_authorised_by_a_holder_and_recorded_as_theirs(db, seeded):
    from tools.grant_legal_authority import grant_first
    holder = make_user(db)
    grant_first(db, holder.email, "test operator")                  # the first holder
    person = make_user(db)
    with pytest.raises(SystemExit, match="does not hold"):
        grant_first(db, person.email, "test operator", make_user(db).email)
    assert grant_first(db, person.email, "test operator", holder.email)
    event = db.execute(select(M.AuditEvent).where(
        M.AuditEvent.action == A.ADMIN_LEGAL_AUTHORITY_GRANTED,
        M.AuditEvent.entity_id == person.id)).scalars().first()
    assert (event.actor_id, event.after_state["authorised_by"]) == (holder.id, holder.email)


def test_the_report_lists_who_decided_what_when_and_why(api, db, owner, case):
    review, evaluation = case
    reviewer = _reviewer(db)
    sign_in(api, db, owner)
    _send(api, review, reviewer)
    sign_in(api, db, reviewer)
    api.post(f"{V1}/evaluations/{evaluation.id}/decisions",
             json={"decision_type": "ACCEPT_DEVIATION", "justification": "small deal"})
    sign_in(api, db, owner)
    decisions = api.get(f"{V1}/reviews/{review.id}/report").json()["data"]["decisions"]
    assert [(d["decision_type"], d["justification"]) for d in decisions] == [
        ("ACCEPT_DEVIATION", "small deal")]
    assert decisions[0]["decided_by_name"] and decisions[0]["decided_at"]
