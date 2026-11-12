"""My To-do — `AM-264` (CLM R8, 2026-11-02): each persona sees only its own items, every
item a fixed sentence and a link, never clause text."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

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
    require_second_person,
    sign_in,
)
from tests.test_version_comparison import V1


def _todo(api, db, user) -> list[dict]:
    sign_in(api, db, user)
    r = api.get(f"{V1}/todo")
    assert r.status_code == 200, r.text
    return r.json()["data"]["items"]


def _kinds(api, db, user) -> set[tuple[str, str]]:
    return {(i["kind"], i["contract_id"]) for i in _todo(api, db, user)}


def _user(db, role):
    u = make_user(db)
    grant_role(db, u, role)
    return u


def _holder(db, tag):
    u = _user(db, P.ROLE_LEGAL_REVIEWER)
    grant(db, u, bespoke_role(db, f"TODO_{tag}_{u.id.hex[:6]}", [P.LEGAL_DECISION]))
    return u


@pytest.fixture
def world(db, seeded, requirement_version):
    owner, stranger = _user(db, P.ROLE_USER), _user(db, P.ROLE_USER)
    a, b = _holder(db, "A"), _holder(db, "B")
    # a point to decide, on the owner's contract, in Legal scope
    review = make_review_for(db, owner)
    review.status = E.ReviewStatus.LEGAL_REVIEW
    finding = make_finding(db, review, requirement_version)
    evaluation = make_evaluation(db, finding, rule_outcome=E.RuleOutcome.UNACCEPTABLE)
    sent = M.ReviewAssignment(review_id=review.id, user_id=a.id, assigned_by=owner.id)
    db.add(sent)                                       # sent to Legal (B11)
    # the owner's other deal: we sent v1, the client returned v2
    returned = make_review_for(db, owner)
    v1 = db.get(M.DocumentVersion, returned.document_version_id)
    v1.doc_metadata = {"version_role": "COMPANY_DRAFT"}
    v1.sent_at, v1.sent_by = datetime.now(UTC) - timedelta(days=2), owner.id
    db.add(M.DocumentVersion(
        contract_id=returned.contract_id, version_number=2, original_filename="v2.pdf",
        mime_type="application/pdf", file_size_bytes=10, file_hash="h2", storage_key="k2",
        processing_status=E.ProcessingStatus.COMPLETED, uploaded_by=owner.id,
        doc_metadata={"version_role": "CLIENT_MODIFIED"}))
    db.flush()
    return {"owner": owner, "stranger": stranger, "a": a, "b": b, "review": review,
            "finding": finding, "evaluation": evaluation, "returned": returned,
            "sent": sent}


def test_each_persona_sees_only_its_own_items(api, db, world):
    deal, returned = str(world["review"].contract_id), str(world["returned"].contract_id)
    assert _kinds(api, db, world["owner"]) == {("client_returned", returned)}
    assert _kinds(api, db, world["stranger"]) == set()
    assert _kinds(api, db, world["a"]) == {("decide", deal)}
    lead = _user(db, P.ROLE_DEPARTMENT_LEAD)            # no legal.decision, not the owner
    assert _kinds(api, db, lead) == set()
    admin = _user(db, P.ROLE_PLATFORM_ADMIN)            # no contract permission at all
    assert _kinds(api, db, admin) == set()


def test_an_item_is_a_fixed_sentence_and_a_readable_link(api, db, world):
    [item] = _todo(api, db, world["owner"])
    assert item["sentence"] == "The client returned a new version — it is our turn."
    assert item["link"] == f"/contracts/{world['returned'].contract_id}/changes"
    assert item["since"] and item["days"] == 0          # since the client's version arrived


def test_a_second_approval_is_owed_by_the_other_holder_only(api, db, world):
    review, finding, ev = world["review"], world["finding"], world["evaluation"]
    require_second_person(db, review, finding)
    sign_in(api, db, world["a"])
    assert api.post(f"{V1}/evaluations/{ev.id}/decisions", json={
        "expected_version": 0, "decision_type": "ACCEPT_DEVIATION",
        "justification": "acceptable"}).status_code == 201
    deal = str(review.contract_id)
    assert ("second_approval", deal) in _kinds(api, db, world["b"])
    assert ("second_approval", deal) not in _kinds(api, db, world["a"])


def test_the_owner_is_told_when_legal_answers_their_escalation(api, db, world):
    finding, ev = world["finding"], world["evaluation"]
    db.add(M.Escalation(finding_id=finding.id, raised_by=world["owner"].id,
                        reason="please look"))
    db.flush()
    deal = str(world["review"].contract_id)
    assert ("answered", deal) not in _kinds(api, db, world["owner"])
    sign_in(api, db, world["a"])
    assert api.post(f"{V1}/evaluations/{ev.id}/decisions", json={
        "expected_version": 0, "decision_type": "REJECT",
        "justification": "not acceptable"}).status_code == 201
    assert ("answered", deal) in _kinds(api, db, world["owner"])
    assert ("answered", deal) not in _kinds(api, db, world["stranger"])


def test_an_archived_contract_waits_on_nobody(api, db, world):
    for key in ("review", "returned"):
        db.get(M.Contract, world[key].contract_id).archived_at = datetime.now(UTC)
    db.flush()
    assert _kinds(api, db, world["owner"]) == set()
    assert _kinds(api, db, world["a"]) == set()


def test_changes_left_to_the_owner_are_counted_and_leave_once_answered(api, db, seeded):
    """A typography-only change is the owner's to answer (`AM-250`); it is on the To-do
    until answered."""
    from tests.test_version_comparison import _version

    owner = _user(db, P.ROLE_USER)
    c = M.Contract(owner_id=owner.id, name="Deal", status=E.ContractStatus.ACTIVE)
    db.add(c)
    db.flush()
    v1 = _version(db, c, 1, [("9", "Fees", '9. Fees are "due" monthly.')])
    v1.doc_metadata, v1.sent_at, v1.sent_by = (
        {"version_role": "COMPANY_DRAFT"}, datetime.now(UTC), owner.id)
    v2 = _version(db, c, 2, [("9", "Fees", "9. Fees are “due” monthly.")])
    v2.doc_metadata = {"version_role": "CLIENT_MODIFIED"}
    db.flush()
    # AM-291: one task per contract per person — the return is folded into it
    [left] = _todo(api, db, owner)
    assert left["kind"] == "changes_to_answer"
    assert left["count"] == 1 and left["sentence"] == "1 of 1 change is yours to answer."
    # ... and every screen reads the same counts from the contract itself
    counts = api.get(f"{V1}/contracts/{c.id}").json()["data"]["counts"]
    assert counts == left["counts"]
    assert counts["changes_total"] == counts["changes_left"] == 1
    assert counts["changes_left_for_me"] == 1
    key = api.get(f"{V1}/contracts/{c.id}/changes").json()["data"]["changes"][0]["row_key"]
    from urllib.parse import quote

    from tests.test_negotiation import _first
    assert api.post(f"{V1}/contracts/{c.id}/changes/{quote(key, safe='')}/answers",
                    json=_first("accept_theirs")).status_code == 201
    assert "changes_to_answer" not in {i["kind"] for i in _todo(api, db, owner)}
    counts = api.get(f"{V1}/contracts/{c.id}").json()["data"]["counts"]
    assert (counts["changes_total"], counts["changes_left"],
            counts["changes_left_for_me"]) == (1, 0, 0)
    listed = api.get(f"{V1}/contracts", params={"scope": "own"}).json()["data"]
    assert [i["counts"] for i in listed if i["id"] == str(c.id)] == [counts]


def test_points_are_counted_once_and_are_for_the_holder_only(api, db, world):
    """`AM-291`: POINTS are the gaps against our standard still undecided, read from the
    same review progress every screen shows; they are "for me" only for a holder."""
    deal = world["review"].contract_id
    sign_in(api, db, world["a"])
    holder = api.get(f"{V1}/contracts/{deal}").json()["data"]["counts"]
    [item] = [i for i in _todo(api, db, world["a"]) if i["kind"] == "decide"]
    assert holder["points_open"] == holder["points_for_me"] == item["count"] >= 1
    sign_in(api, db, world["owner"])
    mine = api.get(f"{V1}/contracts/{deal}").json()["data"]["counts"]
    assert mine["points_open"] == holder["points_open"] and mine["points_for_me"] == 0
    assert "changes_total" not in mine            # no round: absent, never 0


def test_the_round_is_the_clients_version_or_the_one_our_reply_answers():
    from legalmind.api.routers.negotiation import client_version

    def v(n, role=None, **meta):
        return M.DocumentVersion(version_number=n, doc_metadata={
            **({"version_role": role} if role else {}), **meta})
    ours, theirs = v(1, "COMPANY_DRAFT"), v(2, "CLIENT_MODIFIED")
    theirs.id = __import__("uuid").uuid4()
    assert client_version([ours]) is None
    assert client_version([ours, theirs]) is theirs
    reply = v(3, "COMPANY_DRAFT", reply_to=str(theirs.id))
    assert client_version([ours, theirs, reply]) is theirs
    reply.sent_at = datetime.now(UTC)                   # sent: the round is over
    assert client_version([ours, theirs, reply]) is None
    assert client_version([ours, theirs, v(3, "FINAL_SIGNED")]) is None


def test_a_return_whose_open_changes_are_all_legals_is_not_the_owners_task(
        api, db, seeded, monkeypatch):
    from legalmind.api.routers import todo

    owner = _user(db, P.ROLE_USER)
    c = M.Contract(owner_id=owner.id, name="Deal", status=E.ContractStatus.ACTIVE)
    db.add(c)
    db.flush()
    stage = {"stage": "CLIENT_RETURNED", "since": datetime.now(UTC).isoformat(), "days": 0}
    monkeypatch.setattr(todo, "negotiation_stages", lambda g, cs: {x.id: stage for x in cs})
    for counts, kinds in (({"changes_total": 3, "changes_left": 2, "changes_left_for_me": 0},
                           []),
                          # AM-318 A3: every change answered — the final contract is next
                          ({"changes_total": 3, "changes_left": 0, "changes_left_for_me": 0,
                            "points_open": 0, "points_waiting": 0}, ["prepare_final"]),
                          ({}, ["client_returned"])):
        monkeypatch.setattr(todo, "deal_counts", lambda g, cs, n=counts: {x.id: n for x in cs})
        assert [i["kind"] for i in _todo(api, db, owner)] == kinds


def test_a_reply_ready_to_send_is_the_owners_one_task(api, db, seeded, monkeypatch):
    from legalmind.api.routers import todo

    owner = _user(db, P.ROLE_USER)
    c = M.Contract(owner_id=owner.id, name="Deal", status=E.ContractStatus.ACTIVE)
    db.add(c)
    db.flush()
    stage = {"stage": "READY_TO_SEND", "since": datetime.now(UTC).isoformat(), "days": 0}
    monkeypatch.setattr(todo, "negotiation_stages", lambda g, cs: {x.id: stage for x in cs})
    [item] = _todo(api, db, owner)
    assert item["kind"] == "reply_ready" and item["link"] == f"/contracts/{c.id}"


def test_a_review_nobody_sent_to_legal_is_in_no_lawyers_queue(api, db, world):
    """B11: the newer client version's Review, analysed and not sent, waits on its
    owner — the lawyer's queue shows what is with Legal now."""
    world["sent"].revoked_at = datetime.now(UTC)          # withdrawn: nobody sent it
    db.flush()
    assert world["review"].status is E.ReviewStatus.LEGAL_REVIEW   # analysis put it there
    assert _kinds(api, db, world["a"]) == set()
    world["sent"].revoked_at = None                         # sent again
    db.flush()
    assert _kinds(api, db, world["a"]) == {("decide", str(world["review"].contract_id))}


def test_a_signed_contract_waits_on_nobody(api, db, world):
    """B10: once signed, Legal's answer is no task of the owner's."""
    finding, ev = world["finding"], world["evaluation"]
    db.add(M.Escalation(finding_id=finding.id, raised_by=world["owner"].id,
                        reason="please look"))
    db.flush()
    sign_in(api, db, world["a"])
    assert api.post(f"{V1}/evaluations/{ev.id}/decisions", json={
        "expected_version": 0, "decision_type": "REJECT",
        "justification": "not acceptable"}).status_code == 201
    deal = str(world["review"].contract_id)
    assert ("answered", deal) in _kinds(api, db, world["owner"])
    db.get(M.DocumentVersion, world["review"].document_version_id).doc_metadata = {
        "version_role": "FINAL_SIGNED"}
    db.flush()
    assert ("answered", deal) not in _kinds(api, db, world["owner"])


def test_am318_the_closing_tasks_have_their_one_sentence(api, db, seeded, monkeypatch):
    """B3: the owner's "Every change is answered. Prepare the final contract." at Ready
    for the final contract; it clears once the deal is Final."""
    from legalmind.api.routers import todo

    owner = _user(db, P.ROLE_USER)
    c = M.Contract(owner_id=owner.id, name="Deal", status=E.ContractStatus.ACTIVE)
    db.add(c)
    db.flush()
    monkeypatch.setattr(todo, "deal_counts", lambda g, cs: {x.id: {} for x in cs})
    for code, kinds in (("READY_TO_SIGN", ["prepare_final"]), ("FINAL", [])):
        stage = {"stage": code, "since": datetime.now(UTC).isoformat(), "days": 0}
        monkeypatch.setattr(todo, "negotiation_stages",
                            lambda g, cs, s=stage: {x.id: s for x in cs})
        items = _todo(api, db, owner)
        assert [i["kind"] for i in items] == kinds
        if kinds:
            assert items[0]["sentence"] == todo.PREPARE_FINAL


def test_am318_legal_records_the_decision_on_the_contract(api, db, world):
    """B3: every point decided, the Review with this lawyer — "Every point is decided.
    Record the decision on the contract."; gone once the decision is recorded."""
    from legalmind.api.routers import todo
    review = world["review"]
    review.status = E.ReviewStatus.RESOLVED
    db.flush()
    item = next(i for i in _todo(api, db, world["a"]) if i["kind"] == "contract_decision")
    assert item["sentence"] == todo.DECIDE_CONTRACT
    db.add(M.ContractOutcomeRecord(review_id=review.id, outcome=E.ContractOutcome.SIGN_AS_IS,
                                   suggested=E.ContractOutcome.SIGN_AS_IS, justification="ok",
                                   decided_by=world["a"].id, version_number=1))
    db.flush()
    assert all(i["kind"] != "contract_decision" for i in _todo(api, db, world["a"]))
