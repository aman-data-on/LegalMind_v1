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
                       json={"expected_version": 0, "decision_type": "ACCEPT_DEVIATION",
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


def test_the_reviews_list_says_since_when_and_who_holds_it(api, db, owner, case):
    """B3 page 2: the Legal queue's waiting time and assignee — `sent_to_legal()`'s own fact
    (the live assignment), the assignee by name; absent (never null) before it is sent."""
    review, _ = case
    reviewer = _reviewer(db)
    sign_in(api, db, owner)

    def row():
        rows = api.get(f"{V1}/reviews").json()["data"]
        return next(r for r in rows if r["id"] == str(review.id))

    assert "with_legal_since" not in row() and row()["assigned_to"] == []
    _send(api, review, reviewer)
    sent = row()
    assignment = db.execute(select(M.ReviewAssignment).where(
        M.ReviewAssignment.review_id == review.id)).scalar_one()
    assert sent["with_legal_since"] == assignment.created_at.isoformat()
    assert sent["assigned_to"] == [reviewer.name]


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
             json={"expected_version": 0, "decision_type": "ACCEPT_DEVIATION", "justification": "small deal"})
    sign_in(api, db, owner)
    decisions = api.get(f"{V1}/reviews/{review.id}/report").json()["data"]["decisions"]
    assert [(d["decision_type"], d["justification"]) for d in decisions] == [
        ("ACCEPT_DEVIATION", "small deal")]
    assert decisions[0]["decided_by_name"] and decisions[0]["decided_at"]


# ---- AM-173/AM-174 (owner, 2026-10-22): "not applicable", then the decision on the contract
def _decide(api, evaluation, kind, why="reason"):
    return api.post(f"{V1}/evaluations/{evaluation.id}/decisions",
                    json={"expected_version": 0, "decision_type": kind, "justification": why})


def _outcome(api, review, outcome, why="reason", **extra):
    if "expected_version" not in extra:           # AM-177: required; the current version
        extra["expected_version"] = len(api.get(
            f"{V1}/reviews/{review.id}/outcome").json()["data"]["history"])
    return api.post(f"{V1}/reviews/{review.id}/outcome",
                    json={"outcome": outcome, "justification": why, **extra})


def test_not_applicable_closes_the_point_and_resolves_the_review(api, db, owner, case):
    review, evaluation = case
    reviewer = _reviewer(db)
    sign_in(api, db, reviewer)
    done = _decide(api, evaluation, "NOT_APPLICABLE_TO_CONTRACT", "no data is processed here")
    assert done.status_code == 201
    assert (done.json()["data"]["finding_status"], done.json()["data"]["review_status"]) \
        == ("RESOLVED", "RESOLVED")
    # the classification is untouched: a point not applicable is never a MATCH (rule 14)
    db.refresh(evaluation)
    assert evaluation.classification is E.FindingClassification.DEVIATION
    report = api.get(f"{V1}/reviews/{review.id}/report").json()["data"]
    assert report["decisions"][0]["decision_type"] == "NOT_APPLICABLE_TO_CONTRACT"


def test_the_contract_is_decided_only_after_every_point(api, db, owner, case):
    review, _ = case
    sign_in(api, db, _reviewer(db))
    assert api.get(f"{V1}/reviews/{review.id}/outcome").json()["data"]["ready"] is False
    assert _outcome(api, review, "SIGN_AS_IS").status_code == 422


def test_the_reviewer_decides_the_contract_closing_it_with_the_reason_audited(
        api, db, owner, case):
    review, evaluation = case
    reviewer = _reviewer(db)
    sign_in(api, db, owner)
    _send(api, review, reviewer)        # the assignment keeps the decider's access once closed
    sign_in(api, db, reviewer)
    _decide(api, evaluation, "REQUIRE_COMPANY_STANDARD")
    seen = api.get(f"{V1}/reviews/{review.id}/outcome").json()["data"]
    assert (seen["ready"], seen["suggested"], seen["history"]) \
        == (True, "SIGN_WITH_CHANGES", [])
    done = _outcome(api, review, "SIGN_WITH_CHANGES", "send our cap wording back")
    assert done.status_code == 201
    assert done.json()["data"]["review_status"] == "CLOSED"
    event = db.execute(select(M.AuditEvent).where(
        M.AuditEvent.action == A.CONTRACT_OUTCOME_RECORDED)).scalars().one()
    assert (event.actor_id, event.after_state["outcome"],
            event.after_state["justification"]) \
        == (reviewer.id, "SIGN_WITH_CHANGES", "send our cap wording back")
    report = api.get(f"{V1}/reviews/{review.id}/report").json()["data"]
    last = report["contract_outcome"]["history"][-1]
    assert (last["outcome"], last["suggested"], last["decided_by_name"]) \
        == ("SIGN_WITH_CHANGES", "SIGN_WITH_CHANGES", reviewer.name or reviewer.email)
    sign_in(api, db, owner)
    row = next(r for r in api.get(f"{V1}/reviews").json()["data"] if r["id"] == str(review.id))
    assert row["contract_outcome"] == "SIGN_WITH_CHANGES"


def test_on_hold_keeps_the_review_open_and_a_closed_review_never_goes_back(
        api, db, owner, case):
    review, evaluation = case
    reviewer = _reviewer(db)
    sign_in(api, db, owner)
    _send(api, review, reviewer)
    sign_in(api, db, reviewer)
    _decide(api, evaluation, "ACCEPT_DEVIATION")
    held = _outcome(api, review, "ON_HOLD", "waiting for the client's signed copy")
    assert held.json()["data"]["review_status"] == "RESOLVED"
    assert _outcome(api, review, "SIGN_AS_IS", expected_version=0).status_code == 409
    assert _outcome(api, review, "SIGN_AS_IS", expected_version=1) \
        .json()["data"]["review_status"] == "CLOSED"
    assert _outcome(api, review, "ON_HOLD").status_code == 422
    changed = _outcome(api, review, "DO_NOT_SIGN", "client withdrew")
    assert [h["outcome"] for h in changed.json()["data"]["history"]] \
        == ["ON_HOLD", "SIGN_AS_IS", "DO_NOT_SIGN"]


def test_legal_keeps_a_decided_review_until_the_contract_is_decided(api, db, owner, case):
    """REC-09 widened by AM-174: RESOLVED after Legal decided a point stays in Legal scope
    (the contract is still to be decided); CLOSED leaves it, as LEGAL_REVIEW did."""
    review, evaluation = case
    reviewer = _reviewer(db)
    sign_in(api, db, reviewer)
    _decide(api, evaluation, "ACCEPT_DEVIATION")
    assert api.get(f"{V1}/reviews/{review.id}").status_code == 200
    assert str(review.id) in {r["id"] for r in api.get(f"{V1}/reviews").json()["data"]}
    assert _outcome(api, review, "SIGN_AS_IS").json()["data"]["review_status"] == "CLOSED"
    assert api.get(f"{V1}/reviews/{review.id}").status_code == 404


def test_the_owner_never_decides_the_contract(api, db, owner, case):
    review, evaluation = case
    sign_in(api, db, _reviewer(db))
    _decide(api, evaluation, "ACCEPT_DEVIATION")
    sign_in(api, db, owner)
    assert _outcome(api, review, "SIGN_AS_IS").status_code == 403


def test_a_reject_suggests_sign_after_our_changes_and_refuses_sign_as_is(
        api, db, owner, case):
    """AM-396: a Reject reads "this clause must change" — the suggestion is Sign after
    our changes, and Sign as is is refused while the round sends changes back."""
    review, evaluation = case
    reviewer = _reviewer(db)
    sign_in(api, db, owner)
    _send(api, review, reviewer)
    sign_in(api, db, reviewer)
    _decide(api, evaluation, "REJECT")
    seen = api.get(f"{V1}/reviews/{review.id}/outcome").json()["data"]
    assert (seen["suggested"], seen["sign_as_is_allowed"]) == ("SIGN_WITH_CHANGES", False)
    assert _outcome(api, review, "SIGN_AS_IS").status_code == 422
    assert _outcome(api, review, "SIGN_WITH_CHANGES", "send ours back").status_code == 201


def test_an_answer_sending_our_wording_back_counts_in_the_round(db, case):
    """AM-396: the reply's answers on the client version are part of the round."""
    from legalmind.workflow.contract_outcome import changes_go_back
    review, _ = case
    assert changes_go_back(db, review) is False
    db.add(M.ComparisonChoice(left_version_id=None, right_version_id=review.document_version_id,
                              row_key="N|THEIRS|r1", choice="ours", decided_by=review.created_by,
                              version_number=1))
    db.flush()
    assert changes_go_back(db, review) is True


def test_the_note_for_legal_is_carried_to_the_lawyer(api, db, owner, case):
    """AB-213 D3 (`AM-408`): the owner's note travels with the review, audited."""
    review, _ = case
    reviewer = _reviewer(db)
    sign_in(api, db, owner)
    sent = api.post(f"{V1}/reviews/{review.id}/assignments",
                    json={"user_id": str(reviewer.id), "note": "  Please look at 8.3  "})
    assert sent.status_code == 201, sent.text
    sign_in(api, db, reviewer)
    [held] = api.get(f"{V1}/reviews/{review.id}/assignments").json()["data"]["assigned"]
    assert held["note"] == "Please look at 8.3"
    event = db.execute(select(M.AuditEvent).where(
        M.AuditEvent.action == A.REVIEW_ASSIGNED)).scalars().one()
    assert event.after_state["note"] == "Please look at 8.3"


# ---- U2 (AB-225): the lawyer is told, and the owner's note is never lost ------------
def _notices(db, user, kind):
    return db.execute(select(M.Notification).where(
        M.Notification.user_id == user.id, M.Notification.kind == kind)).scalars().all()


def test_each_send_and_take_back_tells_the_lawyer_and_the_inbox_says_only_the_truth(
        api, db, owner, case):
    """AM-472/AM-474 (r2): send (A) → take back (B) → send again (C) writes a notice each
    time, to the lawyer only; writing one marks the opposite unread one read, so the unread
    inbox always matches who holds the contract. A same-kind notice still unread is not
    written twice."""
    from legalmind import notifications as N
    review, _ = case
    reviewer = _reviewer(db)
    contract = db.get(M.Contract, review.contract_id)
    sign_in(api, db, owner)
    _send(api, review, reviewer)                                                   # A
    api.delete(f"{V1}/reviews/{review.id}/assignments/{reviewer.id}")              # B
    _send(api, review, reviewer)                                                   # C
    sent, taken = _notices(db, reviewer, N.SENT_TO_LEGAL), _notices(db, reviewer, N.TAKEN_BACK)
    assert (len(sent), len(taken)) == (2, 1)
    assert _notices(db, owner, N.SENT_TO_LEGAL) == _notices(db, owner, N.TAKEN_BACK) == []
    sign_in(api, db, reviewer)
    unread = [i for i in api.get(f"{V1}/notifications").json()["data"]["items"]
              if i["read_at"] is None and i["kind"] in (N.SENT_TO_LEGAL, N.TAKEN_BACK)]
    assert [i["sentence"] for i in unread] == [
        f"The owner sent {contract.name} to you for Legal review."]
    assert unread[0]["link"] == f"/contracts/{contract.id}"


def test_taking_back_tells_the_lawyer_named_only_while_they_can_read_it(api, db, owner,
                                                                        case):
    """AM-472: one notice to the lawyer it was taken from. Under REC-09 (LEGAL_REVIEW) the
    lawyer still reads the contract, so it is named; where the assignment was the only way
    in (AM-170 r4), the sentence says "a contract" (AM-273 m3)."""
    from legalmind import notifications as N
    review, _ = case
    contract = db.get(M.Contract, review.contract_id)
    reviewer = _reviewer(db)
    sign_in(api, db, owner)
    _send(api, review, reviewer)
    assert api.delete(f"{V1}/reviews/{review.id}/assignments/{reviewer.id}").status_code == 200
    assert len(_notices(db, reviewer, N.TAKEN_BACK)) == 1
    assert _notices(db, owner, N.TAKEN_BACK) == []
    sign_in(api, db, reviewer)
    said = {i["kind"]: i["sentence"] for i in api.get(f"{V1}/notifications").json()["data"]["items"]}
    assert said[N.TAKEN_BACK] == f"The owner took {contract.name} back from Legal."
    # outside Legal scope the assignment was the only basis: no name
    review.status = E.ReviewStatus.ANALYSIS_COMPLETE
    db.flush()
    assert api.get(f"{V1}/contracts/{contract.id}").status_code == 404
    said = {i["kind"]: i["sentence"] for i in api.get(f"{V1}/notifications").json()["data"]["items"]}
    assert said[N.TAKEN_BACK] == "The owner took a contract back from Legal."
    assert contract.name not in str(api.get(f"{V1}/notifications").json())


def test_a_re_send_says_since_the_latest_send_and_a_send_without_a_note_is_kept(
        api, db, owner, case):
    """U2 r2: "With X since" is the newest send, not the revived row's first one; a send
    with no note is still an entry (its note empty), so a re-send never refills a note the
    owner cleared."""
    from datetime import UTC, datetime, timedelta
    review, _ = case
    reviewer = _reviewer(db)
    # the first send, a week ago, and its take-back: rows INSERTED with their own earlier
    # times (the audit trail is append-only — nothing here updates or deletes a row)
    week, day = datetime.now(UTC) - timedelta(days=7), datetime.now(UTC) - timedelta(days=6)
    row = M.ReviewAssignment(review_id=review.id, user_id=reviewer.id, assigned_by=owner.id,
                             note="First", created_at=week, revoked_at=day)
    db.add(row)
    db.add_all([
        M.AuditEvent(actor_id=owner.id, action=A.REVIEW_ASSIGNED, entity_type="review",
                     entity_id=review.id, timestamp=week,
                     after_state={"assigned_to": str(reviewer.id), "note": "First"}),
        M.AuditEvent(actor_id=owner.id, action=A.REVIEW_ASSIGNMENT_WITHDRAWN,
                     entity_type="review", entity_id=review.id, timestamp=day,
                     after_state={"withdrawn_from": str(reviewer.id)})])
    db.flush()
    sign_in(api, db, owner)
    got = _send(api, review, reviewer).json()["data"]
    [held] = got["assigned"]
    assert datetime.fromisoformat(held["assigned_at"]) > week      # L1: the re-send's own time
    assert held["assigned_at"] == got["notes"][0]["sent_at"]
    assert [(n["note"], n["by"]["email"]) for n in got["notes"]] == [("", owner.email),
                                                                    ("First", owner.email)]


def test_every_note_for_legal_is_kept_for_the_owner_only(api, db, owner, case):
    """AM-473: a re-send never loses the earlier note; the owner reads each, with when it
    was taken back; the lawyer's copy has no `notes` key at all (omitted, not nulled)."""
    review, _ = case
    reviewer = _reviewer(db)
    sign_in(api, db, owner)
    api.post(f"{V1}/reviews/{review.id}/assignments",
             json={"user_id": str(reviewer.id), "note": "First: look at 8.3"})
    out = api.delete(f"{V1}/reviews/{review.id}/assignments/{reviewer.id}").json()["data"]
    [first] = out["notes"]
    assert (first["note"], first["to"]["email"]) == ("First: look at 8.3", reviewer.email)
    assert first["taken_back_at"] is not None
    api.post(f"{V1}/reviews/{review.id}/assignments",
             json={"user_id": str(reviewer.id), "note": "Second: and 9.1"})
    notes = api.get(f"{V1}/reviews/{review.id}/assignments").json()["data"]["notes"]
    assert [(n["note"], n["taken_back_at"] is None) for n in notes] == [
        ("Second: and 9.1", True), ("First: look at 8.3", False)]
    sign_in(api, db, reviewer)
    seen = api.get(f"{V1}/reviews/{review.id}/assignments").json()["data"]
    assert "notes" not in seen
    assert seen["assigned"][0]["note"] == "Second: and 9.1"


def test_rule_18_the_lawyer_cannot_take_back_and_out_of_scope_is_the_one_404(api, db,
                                                                             owner, case):
    """Sending and taking back stay the owner's (review.create, owner-resolved): the lawyer
    is refused, a stranger gets the byte-identical 404 a missing review gets (SEC-07)."""
    import uuid
    review, evaluation = case
    reviewer, stranger = _reviewer(db), make_user(db)
    grant_role(db, stranger, P.ROLE_USER)
    sign_in(api, db, owner)
    _send(api, review, reviewer)
    # the owner still never decides their own point (SEC-01)
    assert api.post(f"{V1}/evaluations/{evaluation.id}/decisions",
                    json={"expected_version": 0, "decision_type": "ACCEPT_DEVIATION",
                          "justification": "x"}).status_code in (403, 404)
    sign_in(api, db, reviewer)
    assert api.delete(f"{V1}/reviews/{review.id}/assignments/{reviewer.id}").status_code \
        in (403, 404)
    sign_in(api, db, stranger)
    hidden = api.get(f"{V1}/reviews/{review.id}/assignments")
    missing = api.get(f"{V1}/reviews/{uuid.uuid4()}/assignments")
    assert hidden.status_code == missing.status_code == 404
    # byte-identical but for the per-request correlation id (as test_api_authz does)
    def strip(r):
        return {k: v for k, v in r.json()["error"].items() if k != "request_id"}
    assert strip(hidden) == strip(missing)


def test_l4_who_reads_the_owners_notes(api, db, owner, case):
    """U2 r4 (L4): `notes` is the owner's alone. Others who may see the review get the
    assignments without the key (omitted, never nulled); those who may not get the one 404;
    after a transfer the new owner reads them and the old one is out of scope."""
    import uuid as _uuid
    review, _ = case
    sales = M.Department(code=f"D{_uuid.uuid4().hex[:8]}", name="Sales")
    db.add(sales)
    db.flush()
    lead, mate, colleague, admin, successor = (make_user(db) for _ in range(5))
    for u in (owner, lead, mate, colleague, successor):
        u.department_id = sales.id
    for u in (mate, colleague, successor):
        grant_role(db, u, P.ROLE_USER)
    grant_role(db, lead, P.ROLE_DEPARTMENT_LEAD)
    grant_role(db, admin, P.ROLE_PLATFORM_ADMIN)
    db.add(M.ContractCollaborator(contract_id=review.contract_id, user_id=mate.id,
                                  added_by=owner.id))
    lawyer, other_lawyer = _reviewer(db, "A"), _reviewer(db, "B")
    db.flush()
    sign_in(api, db, owner)
    api.post(f"{V1}/reviews/{review.id}/assignments",
             json={"user_id": str(lawyer.id), "note": "Owner's note"})
    url = f"{V1}/reviews/{review.id}/assignments"
    assert api.get(url).json()["data"]["notes"][0]["note"] == "Owner's note"
    for who in (lead, mate, other_lawyer, lawyer):
        sign_in(api, db, who)
        got = api.get(url)
        assert got.status_code == 200, who.email
        assert "notes" not in got.json()["data"], who.email
    for who in (admin, colleague):
        sign_in(api, db, who)
        assert api.get(url).status_code == 404, who.email
    # a transfer: the new owner reads the notes; the old owner is out of scope
    contract = db.get(M.Contract, review.contract_id)
    contract.owner_id = successor.id
    db.flush()
    sign_in(api, db, successor)
    assert api.get(url).json()["data"]["notes"][0]["note"] == "Owner's note"
    sign_in(api, db, owner)
    assert api.get(url).status_code == 404


def test_m1_a_send_and_take_back_loop_never_floods_the_lawyers_mail(
        api, db, owner, case, tmp_path, monkeypatch):
    """U2 r4 (M1): a take-back is in-app only; a send e-mails at most once per 15 minutes
    per lawyer per contract. Every in-app notice is still written."""
    from legalmind import notifications as N
    monkeypatch.setenv("LEGALMIND_MAIL_SINK_DIR", str(tmp_path / "sink"))
    review, _ = case
    reviewer = _reviewer(db)
    sign_in(api, db, owner)
    for _ in range(5):
        _send(api, review, reviewer)
        api.delete(f"{V1}/reviews/{review.id}/assignments/{reviewer.id}")
    mails = list((tmp_path / "sink").glob("*.eml"))          # each request commits
    assert len(mails) == 1 and reviewer.email in mails[0].read_text()
    assert len(_notices(db, reviewer, N.SENT_TO_LEGAL)) == 5
    assert len(_notices(db, reviewer, N.TAKEN_BACK)) == 5


def test_l1_the_list_the_progress_and_the_workspace_agree_on_since(api, db, owner, case):
    """U2 r4 (L1): a re-send writes created_at = now(), so "with Legal since" is the same
    instant on the contracts list, the review progress and the assignments."""
    from datetime import UTC, datetime, timedelta
    review, _ = case
    reviewer = _reviewer(db)
    week = datetime.now(UTC) - timedelta(days=7)
    db.add(M.ReviewAssignment(review_id=review.id, user_id=reviewer.id, assigned_by=owner.id,
                              created_at=week, revoked_at=week + timedelta(days=1)))
    db.flush()
    sign_in(api, db, owner)
    [held] = _send(api, review, reviewer).json()["data"]["assigned"]
    assert held["assigned_at"] > week.isoformat()
    row = db.execute(select(M.ReviewAssignment)).scalars().one()
    assert row.created_at.isoformat() == held["assigned_at"]
    # the reviews list and the contract's own stage read the same row
    listed = api.get(f"{V1}/reviews").json()["data"]
    [mine] = [r for r in listed if r["id"] == str(review.id)]
    stage = api.get(f"{V1}/contracts/{review.contract_id}").json()["data"]["negotiation_stage"]
    assert mine["with_legal_since"][:19] == held["assigned_at"][:19]
    assert stage["stage"] != "INTERNAL_REVIEW" or stage["since"][:19] == held["assigned_at"][:19]
