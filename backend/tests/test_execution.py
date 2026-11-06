"""The closing step — stamp duty, who signed, the signed copy, "Mark signed"
(CLM flow 5 "Final"; `AM-292`, `AM-297`, `AM-276`).

Every rule pinned: the decision gate, undecided points, the stamp (or the recorded
"not stamped yet" acknowledgement), both parties' authority, the signed copy compared
with the agreed version (a difference blocks unless a `legal.decision` holder accepts it
with a reason), append-only history with expected_version, the record final after
signing, the stage SIGNED, delete refused, FINAL_SIGNED never by declaration, audit.
LegalMind computes no duty: what is typed is stored. Every document here is synthetic.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.security import audit
from legalmind.security import permissions as P
from tests.conftest import grant_role, make_user, sign_in
from tests.test_negotiation import (  # noqa: F401 — `owner` is a fixture
    _contract,
    _docx,
    _ingest,
    _mark,
    _review,
    owner,
)
from tests.test_version_comparison import V1

AGREED = ["1. Fees are payable within 30 days of invoice.",
          "2. This Agreement is governed by the laws of India."]
EXEC = f"{V1}/contracts/{{}}/execution"
SIGN = f"{V1}/contracts/{{}}/mark-signed"
PEOPLE = [{"party": "OURS", "name": "A Signer", "designation": "Director",
           "authority_kind": "BOARD_RESOLUTION", "authority_reference": "BR 12/2026",
           "authority_date": "2026-10-01", "signed_on": "2026-11-03", "method": "WET_INK"},
          {"party": "CLIENT", "name": "B Signer", "designation": "CFO",
           "authority_kind": "AUTHORITY_LETTER", "authority_reference": "Letter 3 Oct 2026"}]
STAMP = {"stamp_method": "E_STAMP", "stamp_reference": "IN-MH12345678901234X",
         "stamp_state": "Maharashtra", "duty_paid": "₹500 (as typed)",
         "stamped_on": "2026-11-02"}


def _decide(db, review, outcome=E.ContractOutcome.SIGN_AS_IS):
    db.add(M.ContractOutcomeRecord(review_id=review.id, outcome=outcome, suggested=outcome,
                                   justification="agreed", decided_by=review.created_by,
                                   version_number=1))
    db.flush()


def _ready(db, owner, tmp_path, signed_text=AGREED):
    """A contract whose agreed version is decided Sign as is, and a signed copy."""
    c = _contract(db, owner)
    agreed = _ingest(db, tmp_path, c, _docx(*AGREED), "agreed.docx")
    review = _review(db, agreed, [])
    _decide(db, review)
    signed = _ingest(db, tmp_path, c, _docx(*signed_text), "signed.docx")
    return c, agreed, review, signed


def _record(api, c, signed, **fields):
    body = {**STAMP, "signatories": PEOPLE, "signed_document_version_id": str(signed.id),
            **fields}
    r = api.post(EXEC.format(c.id), json=body)
    assert r.status_code == 201, r.text
    return r.json()["data"]


def _codes(state):
    return {b["code"] for b in state["blockers"]}


def _stage(api, c):
    return api.get(f"{V1}/contracts/{c.id}").json()["data"]["negotiation_stage"]["stage"]


def test_a_complete_record_on_a_matching_copy_signs_the_contract(api, db, owner, tmp_path):
    c, agreed, _, signed = _ready(db, owner, tmp_path)
    state = _record(api, c, signed)
    assert state["blockers"] == [] and state["comparison"]["status"] == "MATCHES"
    assert state["agreed"]["document_version_id"] == str(agreed.id)
    assert _stage(api, c) == "READY_TO_SIGN"        # the named signed copy is read past
    r = api.post(SIGN.format(c.id), json={"document_version_id": str(signed.id),
                                          "expected_version": 1})
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["signed"] and body["execution"]["signed_at"]
    assert body["execution"]["duty_paid"] == "₹500 (as typed)"     # never computed
    assert body["document_version"]["version_role"] == "FINAL_SIGNED"
    assert _stage(api, c) == "SIGNED"
    events = [e.action for e in db.scalars(select(M.AuditEvent).where(
        M.AuditEvent.entity_id == c.id))]
    assert audit.EXECUTION_RECORDED in events and audit.CONTRACT_SIGNED in events
    signed_event = db.scalars(select(M.AuditEvent).where(
        M.AuditEvent.action == audit.CONTRACT_SIGNED)).one()
    assert "A Signer" not in str(signed_event.after_state)      # no names in the audit
    assert signed_event.after_state["file_hash"] == signed.file_hash


def test_a_copy_of_our_marked_up_reply_matches_it(api, db, owner, tmp_path):
    """Our reply carries whole clauses as tracked insertions; a signed copy of that same
    file is the same text — not a clause "moved in" (the change detection's own fix)."""
    marked = [AGREED[0], [_mark("ins", "3. A clause our reply inserted.", 1)], AGREED[1]]
    c = _contract(db, owner)
    agreed = _ingest(db, tmp_path, c, _docx(*marked), "reply.docx")
    _decide(db, _review(db, agreed, []))
    signed = _ingest(db, tmp_path, c, _docx(*marked), "signed.docx")
    assert _record(api, c, signed)["comparison"]["status"] == "MATCHES"


def test_mark_signed_refuses_without_the_decision(api, db, owner, tmp_path):
    c = _contract(db, owner)
    agreed = _ingest(db, tmp_path, c, _docx(*AGREED), "agreed.docx")
    review = _review(db, agreed, [])
    _decide(db, review, E.ContractOutcome.ON_HOLD)
    signed = _ingest(db, tmp_path, c, _docx(*AGREED), "signed.docx")
    _record(api, c, signed)
    r = api.post(SIGN.format(c.id), json={"document_version_id": str(signed.id),
                                          "expected_version": 1})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "SIGNING_NOT_READY"
    assert {b["code"] for b in r.json()["error"]["blockers"]} == {"NOT_DECIDED"}


def test_a_reopened_decision_or_an_undecided_point_blocks(api, db, owner, tmp_path):
    c, agreed, review, signed = _ready(db, owner, tmp_path)
    state = _record(api, c, signed)
    assert not state["blockers"]
    finding = _review(db, agreed, [(0, E.FindingClassification.DEVIATION,
                                    E.RuleOutcome.UNACCEPTABLE)])
    # the newer Review on the agreed version has no decision and one open point (one
    # transaction gives both Reviews the same now(): the newer is dated after)
    finding.created_at = review.created_at + timedelta(seconds=1)
    db.flush()
    db.execute(text("UPDATE findings SET status = 'DECISION_REQUIRED' "
                    "WHERE review_id = :r"), {"r": finding.id})
    state = api.get(EXEC.format(c.id)).json()["data"]
    assert {"NOT_DECIDED", "OPEN_POINTS"} <= _codes(state)


def test_stamp_and_both_authorities_are_required(api, db, owner, tmp_path):
    c, _, _, signed = _ready(db, owner, tmp_path)
    r = api.post(EXEC.format(c.id), json={"stamp_method": "E_STAMP",
                                          "signatories": PEOPLE[:1]})
    # (the uploaded copy, not yet named as signed, is the latest version: NOT_DECIDED too)
    assert {"STAMP_MISSING", "AUTHORITY_MISSING_CLIENT", "NO_SIGNED_COPY"} \
        <= _codes(r.json()["data"])
    r = api.patch(EXEC.format(c.id), json={"expected_version": 1, "signatories": [
        PEOPLE[0], {**PEOPLE[1], "authority_reference": None}]})
    assert "AUTHORITY_MISSING_CLIENT" in _codes(r.json()["data"])


def test_not_stamped_needs_the_recorded_acknowledgement(api, db, owner, tmp_path):
    c, _, _, signed = _ready(db, owner, tmp_path)
    state = _record(api, c, signed, stamp_method="NOT_STAMPED")
    assert _codes(state) == {"STAMP_NOT_ACKNOWLEDGED"}
    r = api.patch(EXEC.format(c.id), json={"expected_version": 1,
                                           "not_stamped_acknowledged": True})
    state = r.json()["data"]
    assert state["blockers"] == [] and state["execution"]["not_stamped_acknowledged"]
    assert state["execution"]["stamp_reference"] is None     # no stamp beside "none"
    row = db.scalars(select(M.Execution).where(M.Execution.contract_id == c.id)
                     .order_by(M.Execution.version_number.desc())).first()
    assert row.not_stamped_ack_by == owner.id
    # choosing a stamp method again clears the acknowledgement
    r = api.patch(EXEC.format(c.id), json={"expected_version": 2, **STAMP})
    assert r.json()["data"]["execution"]["not_stamped_acknowledged"] is False


def test_a_different_signed_copy_blocks_until_a_holder_accepts(api, db, owner, tmp_path):
    c, _, review, signed = _ready(db, owner, tmp_path, signed_text=[
        AGREED[0], "2. This Agreement is governed by the laws of Singapore."])
    state = _record(api, c, signed)
    assert state["comparison"]["status"] == "DIFFERS"
    assert state["comparison"]["differences"][0]["clause"]["number"] == "2"
    assert _codes(state) == {"COPY_DIFFERS"}
    accept = f"{EXEC.format(c.id)}/accept-differences"
    # the owner holds no legal.decision: the holder's act is refused
    assert api.post(accept, json={"expected_version": 1, "reason": "ok"}).status_code \
        in (403, 404)
    lawyer = make_user(db)
    grant_role(db, lawyer, P.ROLE_LEGAL_REVIEWER)
    grant_role(db, lawyer, P.ROLE_LEGAL_DECISION_AUTHORITY)
    db.add(M.ReviewAssignment(review_id=review.id, user_id=lawyer.id, assigned_by=owner.id))
    db.flush()
    sign_in(api, db, lawyer)
    assert api.post(accept, json={"expected_version": 1, "reason": "  "}).status_code == 422
    r = api.post(accept, json={"expected_version": 1,
                               "reason": "Signatory initialled the governing-law change"})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["blockers"] == []
    sign_in(api, db, owner)
    r = api.post(SIGN.format(c.id), json={"document_version_id": str(signed.id),
                                          "expected_version": 2})
    assert r.status_code == 200, r.text


def test_a_new_signed_copy_drops_an_earlier_acceptance(api, db, owner, tmp_path):
    c, _, _, signed = _ready(db, owner, tmp_path)
    _record(api, c, signed)
    db.add(M.Execution(contract_id=c.id, version_number=2, recorded_by=owner.id,
                       signatories=PEOPLE, signed_document_version_id=signed.id,
                       differences_accepted_by=owner.id, differences_reason="x", **{
                           k: v for k, v in STAMP.items() if k != "stamped_on"}))
    db.flush()
    other = _ingest(db, tmp_path, c, _docx("1. Something else entirely."), "other.docx")
    r = api.patch(EXEC.format(c.id), json={"expected_version": 2,
                                           "signed_document_version_id": str(other.id)})
    assert r.json()["data"]["execution"]["differences_accepted"] is False


def test_saves_are_append_only_and_name_their_version(api, db, owner, tmp_path):
    c, _, _, signed = _ready(db, owner, tmp_path)
    _record(api, c, signed)
    assert api.post(EXEC.format(c.id), json={}).status_code == 409   # one record
    assert api.patch(EXEC.format(c.id), json={"expected_version": 5,
                                              "duty_paid": "x"}).status_code == 409
    assert api.patch(EXEC.format(c.id), json={"expected_version": 1,
                                              "duty_paid": "₹600"}).status_code == 200
    rows = db.scalars(select(M.Execution).where(M.Execution.contract_id == c.id)
                      .order_by(M.Execution.version_number)).all()
    assert [(r.version_number, r.duty_paid) for r in rows] == [
        (1, "₹500 (as typed)"), (2, "₹600")]
    with pytest.raises(DBAPIError), db.begin_nested():
        db.execute(text("UPDATE executions SET duty_paid = 'y' WHERE id = :i"),
                   {"i": rows[0].id})


def test_the_record_is_final_after_signing(api, db, owner, tmp_path):
    c, _, _, signed = _ready(db, owner, tmp_path)
    _record(api, c, signed)
    assert api.post(SIGN.format(c.id), json={"document_version_id": str(signed.id),
                                             "expected_version": 1}).status_code == 200
    r = api.patch(EXEC.format(c.id), json={"expected_version": 2, "duty_paid": "x"})
    assert r.status_code == 409
    with pytest.raises(DBAPIError), db.begin_nested():
        db.add(M.Execution(contract_id=c.id, version_number=3, recorded_by=owner.id,
                           signatories=[]))
        db.flush()


def test_a_signed_contract_is_archived_never_deleted(api, db, owner, tmp_path):
    c, _, _, signed = _ready(db, owner, tmp_path)
    _record(api, c, signed)      # even a draft execution record holds it (AM-276)
    r = api.delete(f"{V1}/contracts/{c.id}")
    assert r.status_code == 409 and "archive" in r.json()["error"]["message"]
    assert api.post(f"{V1}/contracts/{c.id}/archive").status_code == 200


def test_final_signed_is_never_declared(api, db, owner, tmp_path):
    c, _, _, signed = _ready(db, owner, tmp_path)
    r = api.patch(f"{V1}/document-versions/{signed.id}", json={"version_role": "FINAL_SIGNED"})
    assert r.status_code == 409 and "Record signing" in r.json()["error"]["message"]


def test_prefill_comes_from_the_client_profile(api, db, owner, tmp_path):
    c, _, _, _ = _ready(db, owner, tmp_path)
    cp = M.Counterparty(name="Client Co", created_by=owner.id, signatory_name="C Person",
                        signatory_designation="Director", authority_reference="BR 1")
    db.add(cp)
    db.flush()
    c.counterparty_id = cp.id
    db.flush()
    state = api.get(EXEC.format(c.id)).json()["data"]
    client = next(s for s in state["prefill"]["signatories"] if s["party"] == "CLIENT")
    assert (client["name"], client["designation"], client["authority_reference"]) == (
        "C Person", "Director", "BR 1")
    assert state["execution"] is None and "NO_RECORD" in _codes(state)


def test_an_outsider_sees_nothing(api, db, owner, tmp_path):
    c, _, _, _ = _ready(db, owner, tmp_path)
    stranger = make_user(db)
    grant_role(db, stranger, P.ROLE_USER)
    sign_in(api, db, stranger)
    assert api.get(EXEC.format(c.id)).status_code == 404
    assert api.post(EXEC.format(c.id), json={}).status_code == 404


# ------------------------------------------------- filed as signed (AM-298)
def _filed(api, db, owner, tmp_path):
    c = _contract(db, owner)
    executed = _ingest(db, tmp_path, c, _docx(*AGREED), "executed.docx")
    r = api.patch(f"{V1}/document-versions/{executed.id}",
                  json={"version_role": "FINAL_SIGNED"})
    assert r.status_code == 200, r.text
    return c, executed


def test_a_contract_signed_outside_is_filed_as_signed(api, db, owner, tmp_path):
    c, executed = _filed(api, db, owner, tmp_path)
    assert _stage(api, c) == "SIGNED"
    state = api.get(EXEC.format(c.id)).json()["data"]
    assert state["signed"] and state["confirmed"] is False and state["blockers"] == []
    assert state["execution"]["origin"] == "SIGNED_OUTSIDE"
    assert state["execution"]["signed_document_version_id"] == str(executed.id)
    # optional details added afterwards, then confirmed — never blocked
    r = api.patch(EXEC.format(c.id), json={"expected_version": 1, **STAMP})
    assert r.status_code == 200 and r.json()["data"]["execution"]["duty_paid"] == STAMP[
        "duty_paid"]
    other = _ingest(db, tmp_path, c, _docx("x"), "other.docx")
    assert api.patch(EXEC.format(c.id), json={
        "expected_version": 2, "signed_document_version_id": str(other.id)}).status_code == 409
    r = api.post(SIGN.format(c.id), json={"document_version_id": str(executed.id),
                                          "expected_version": 2})
    assert r.status_code == 200 and r.json()["data"]["confirmed"] is True
    assert api.patch(EXEC.format(c.id), json={"expected_version": 3,
                                              "duty_paid": "y"}).status_code == 409
    # its copy stays signed; delete refused, archive allowed
    assert api.patch(f"{V1}/document-versions/{executed.id}",
                     json={"version_role": None}).status_code == 409
    assert api.delete(f"{V1}/contracts/{c.id}").status_code == 409
    assert api.post(f"{V1}/contracts/{c.id}/archive").status_code == 200
    actions = set(db.execute(select(M.AuditEvent.action).where(
        M.AuditEvent.entity_id == c.id)).scalars())
    assert {audit.EXECUTION_RECORDED, audit.CONTRACT_SIGNED} <= actions


def test_a_negotiated_contract_is_never_filed_as_signed(api, db, owner, tmp_path):
    c = _contract(db, owner)
    theirs = _ingest(db, tmp_path, c, _docx(*AGREED), "theirs.docx")
    assert api.patch(f"{V1}/document-versions/{theirs.id}",
                     json={"version_role": "CLIENT_MODIFIED"}).status_code == 200
    executed = _ingest(db, tmp_path, c, _docx(*AGREED), "executed.docx")
    r = api.patch(f"{V1}/document-versions/{executed.id}",
                  json={"version_role": "FINAL_SIGNED"})
    assert r.status_code == 409 and "Mark signed" in r.json()["error"]["message"]
    assert _role_of(db, executed) is None and _stage(api, c) != "SIGNED"


def _role_of(db, version):
    db.refresh(version)
    return (version.doc_metadata or {}).get("version_role")


def test_a_version_declared_signed_before_the_signing_step_still_reads_signed(
        api, db, owner, tmp_path):
    c = _contract(db, owner)
    legacy = _ingest(db, tmp_path, c, _docx(*AGREED), "legacy.docx")
    legacy.doc_metadata = {"version_role": "FINAL_SIGNED"}      # as stored before AM-292
    db.flush()
    assert _stage(api, c) == "SIGNED"
    state = api.get(EXEC.format(c.id)).json()["data"]
    assert state == {"execution": None, "blockers": [], "comparison": None,
                     "signed": True, "legacy": True}
    assert api.post(EXEC.format(c.id), json={}).status_code == 409
    assert api.delete(f"{V1}/contracts/{c.id}").status_code == 409
    assert api.post(f"{V1}/contracts/{c.id}/archive").status_code == 200


def test_a_replaced_wrong_copy_never_becomes_the_agreed_version(api, db, owner, tmp_path):
    """"Upload a different copy": the discarded copy stays named on an older record row,
    and is never read as the agreed text — by the signing step or by the stage."""
    c, agreed, _, wrong = _ready(db, owner, tmp_path, signed_text=[
        AGREED[0], "2. This Agreement is governed by the laws of Singapore."])
    assert _codes(_record(api, c, wrong)) == {"COPY_DIFFERS"}
    right = _ingest(db, tmp_path, c, _docx(*AGREED), "right.docx")
    state = api.patch(EXEC.format(c.id), json={
        "expected_version": 1, "signed_document_version_id": str(right.id)}).json()["data"]
    assert state["agreed"]["document_version_id"] == str(agreed.id)
    assert state["comparison"]["status"] == "MATCHES" and state["blockers"] == []
    assert _stage(api, c) == "READY_TO_SIGN"
    r = api.post(SIGN.format(c.id), json={"document_version_id": str(right.id),
                                          "expected_version": 2})
    assert r.status_code == 200, r.text


def test_a_signed_contract_takes_no_negotiation_write(api, db, owner, tmp_path):
    c, agreed, _, signed = _ready(db, owner, tmp_path)
    _record(api, c, signed)
    assert api.post(SIGN.format(c.id), json={"document_version_id": str(signed.id),
                                             "expected_version": 1}).status_code == 200
    refused = [
        api.post(f"{V1}/contracts/{c.id}/document-versions", content=_docx(*AGREED),
                 headers={"X-Filename": "late.docx", "Content-Type":
                          "application/vnd.openxmlformats-officedocument."
                          "wordprocessingml.document"}),
        api.post(f"{V1}/document-versions/{agreed.id}/mark-sent"),
        api.post(f"{V1}/contracts/{c.id}/reply"),
        api.post(f"{V1}/contracts/{c.id}/changes/accept", json={"effect": "POSITIVE", "row_keys": ["x"]}),
    ]
    for r in refused:
        assert r.status_code == 409, r.text
        assert r.json()["error"]["message"] == (
            "This contract is signed. Changes after signing go in an amendment.")
    assert db.scalar(select(M.DocumentVersion.id).where(
        M.DocumentVersion.original_filename == "late.docx")) is None
    # the Changes tab offers no write either (presentation, as the 409)
    changes = api.get(f"{V1}/contracts/{c.id}/changes").json()["data"]
    assert changes["can_answer"] is False and changes["can_send"] is False


def test_analysing_the_signed_copy_never_supersedes_the_agreed_review(
        api, db, owner, tmp_path):
    """The signed copy is read past: its own analysed Review leaves the agreed version's
    Review writable (AM-178 is about a newer version of the deal, not its signed copy)."""
    from legalmind.workflow.review_lifecycle import is_superseded, require_writable
    c, _, review, signed = _ready(db, owner, tmp_path)
    _record(api, c, signed)
    _review(db, signed, [])                  # someone analyses the signed copy
    assert is_superseded(db, review) is None
    require_writable(db, review)


def test_a_reviewed_version_is_never_named_the_signed_copy(api, db, owner, tmp_path):
    """Locked 33.7: what a version is (its role) is fixed once it has a Review, and
    "Mark signed" would declare it FINAL_SIGNED — refused when named and when signing."""
    c, _, _, signed = _ready(db, owner, tmp_path)
    _record(api, c, signed)
    _review(db, signed, [])
    r = api.patch(EXEC.format(c.id), json={"expected_version": 1,
                                           "signed_document_version_id": str(signed.id)})
    assert r.status_code == 409 and "has been reviewed" in r.json()["error"]["message"]
    r = api.post(SIGN.format(c.id), json={"document_version_id": str(signed.id),
                                          "expected_version": 1})
    assert r.status_code == 409 and "has been reviewed" in r.json()["error"]["message"]
    assert signed.doc_metadata.get("version_role") != "FINAL_SIGNED"


def test_the_signed_copy_is_never_reviewed(api, db, owner, tmp_path):
    """M1/L2: the copy named on the signing record is filed, not analysed — so it never
    supersedes the agreed Review, and "Mark signed" can still declare it."""
    import uuid
    c, _, _, signed = _ready(db, owner, tmp_path)
    _record(api, c, signed)
    r = api.post(f"{V1}/reviews", json={"document_version_id": str(signed.id),
                                        "configuration_snapshot_id": str(uuid.uuid4())})
    assert r.status_code == 409 and "signed copy" in r.json()["error"]["message"]
