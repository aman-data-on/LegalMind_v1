"""CLM slice S2 — the lawyer's access, "Write our wording", our standard, the notes,
the own-contract second approver and the download/send gate (AB-152, 2026-11-03).

`AM-288` the lawyer reads and negotiates on contracts sent to Legal, assigned to them or
created by them — never globally (the byte-identical 404); `AM-284` our wording is
decided before the reply (an APPROVE_CUSTOMIZATION carrying its SHA-256), the note to
the client becomes a Word comment; `AM-285` the internal note is omitted, never nulled,
and never leaves LegalMind; `AM-289` a decision on one's own contract waits for a
second, different holder; `AM-290` client paper first; `AM-293` nothing undecided is
downloaded or sent. Every document and clause here is synthetic — structural text that
asserts no legal position (rule 21).
"""

from __future__ import annotations

import io
import uuid
import zipfile
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.drafting.reply_plan import Answer, reply_rows, sha256
from legalmind.security import permissions as P
from tests.conftest import (
    grant_role,
    make_user,
    sign_in,
    without_legal_position,
)
from tests.test_negotiation import (  # noqa: F401 — `owner` is a fixture
    _changes,
    _contract,
    _docx,
    _first,
    _ingest,
    _review,
    _url,
    owner,
)
from tests.test_version_comparison import V1

OURS = "9. Liability is capped at 12 months of fees."
THEIRS = "9. Liability is capped at 3 months of fees."
WORDING = "9. Liability is capped at 12 months of fees.\n9A. This cap applies to each party."
REPLY = f"{V1}/contracts/{{}}/reply"
NOTE, SECRET = "We keep our cap.", "Internal: the client asked twice."


@pytest.fixture(autouse=True)
def published(db, owner):
    """A published (empty) configuration, older than any a test makes: our reply is
    reviewed when prepared, so the gate can open."""
    db.add(M.ConfigurationSnapshot(snapshot_hash=uuid.uuid4().hex, created_by=owner.id,
                                   created_at=datetime.now(UTC) - timedelta(days=1)))
    db.flush()


def _lawyer(db):
    """Legal Reviewer + Legal Decision Authority — no `contract.update` at all."""
    user = make_user(db)
    grant_role(db, user, P.ROLE_LEGAL_REVIEWER)
    grant_role(db, user, P.ROLE_LEGAL_DECISION_AUTHORITY)
    return user


def _measured(db, tmp_path, owner):
    """Our clause 9, the client's cheaper cap — measured: one DEVIATION on theirs."""
    c = _contract(db, owner)
    _ingest(db, tmp_path, c, _docx(OURS), "ours.docx")
    theirs = _ingest(db, tmp_path, c, _docx(THEIRS), "theirs.docx")
    review = _review(db, theirs, [(0, E.FindingClassification.DEVIATION,
                                   E.RuleOutcome.UNACCEPTABLE)])
    return c, theirs, review


def _send(db, review, user):
    db.add(M.ReviewAssignment(review_id=review.id, user_id=user.id,
                              assigned_by=review.created_by))
    db.flush()


def _wording(api, c, change, **extra):
    seen = (change["answer"] or {}).get("version_number", 0)
    return api.post(_url(c, change["row_key"]), json={
        "answer": "write_wording", "wording": WORDING, "reason": "our cap stands",
        "client_note": NOTE, "internal_note": SECRET, "expected_version": seen, **extra})


def _read(docx_bytes: bytes) -> list[str]:
    """The reply as a reader of the marked-up copy sees it (accepted view)."""
    from legalmind.ingestion.parsing import parse_docx
    return [s.content for s in parse_docx(docx_bytes).segments]


def _no_key(obj, key):
    """``key`` is absent everywhere in ``obj`` — omitted, never nulled (SEC-07)."""
    if isinstance(obj, dict):
        assert key not in obj
        for v in obj.values():
            _no_key(v, key)
    elif isinstance(obj, list):
        for v in obj:
            _no_key(v, key)


# ---------------------------------------------------------------- AM-288 access
def test_a_lawyer_reads_and_answers_a_contract_sent_to_them_and_nothing_else(
        api, db, owner, tmp_path):
    c, _, review = _measured(db, tmp_path, owner)
    other, _, _ = _measured(db, tmp_path, owner)           # never sent to anyone
    lawyer = _lawyer(db)
    _send(db, review, lawyer)
    sign_in(api, db, lawyer)
    listed = _changes(api, c)
    assert listed["can_answer"] and listed["can_write_wording"]
    change = listed["changes"][0]
    r = api.post(_url(c, change["row_key"]), json=_first("keep_ours"))
    assert r.status_code == 201, r.text
    # no global Legal read: the unrelated contract is the byte-identical 404
    hidden = api.get(_url(other))
    absent = api.get(f"{V1}/contracts/{uuid.uuid4()}/changes")
    assert hidden.status_code == absent.status_code == 404
    strip = lambda r: {k: v for k, v in r.json()["error"].items() if k != "request_id"}  # noqa: E731
    assert strip(hidden) == strip(absent)
    assert api.post(_url(other, "N|x||"), json=_first("keep_ours")).status_code == 404


def test_a_reader_without_the_decision_right_reads_but_does_not_negotiate(
        api, db, owner, tmp_path):
    c, _, review = _measured(db, tmp_path, owner)
    reader = make_user(db)
    grant_role(db, reader, P.ROLE_LEGAL_REVIEWER)
    _send(db, review, reader)
    sign_in(api, db, reader)
    listed = _changes(api, c)
    assert listed["can_answer"] is False
    r = api.post(_url(c, listed["changes"][0]["row_key"]), json=_first("keep_ours"))
    assert r.status_code == 404


def test_a_lawyer_who_created_a_contract_still_reads_it_after_a_transfer(
        api, db, owner, tmp_path):
    """`AM-288` r1(c): created by them — ownership moved on, the creation did not."""
    lawyer = _lawyer(db)
    c = _contract(db, lawyer)
    _ingest(db, tmp_path, c, _docx(OURS), "ours.docx")
    _ingest(db, tmp_path, c, _docx(THEIRS), "theirs.docx")
    c.owner_id = owner.id
    db.flush()
    sign_in(api, db, lawyer)
    assert api.get(f"{V1}/contracts/{c.id}").status_code == 200
    assert _changes(api, c)["can_answer"] is True


def test_legal_lists_what_it_may_read_and_nothing_else(api, db, owner, tmp_path):
    """`AM-288` on the list (`scope=legal`): sent to them, created by them, or in Legal
    scope — every row one a GET opens; an unrelated contract is not listed (no global
    read), and the scope needs `legal.review`."""
    sent, _, review = _measured(db, tmp_path, owner)
    other, _, _ = _measured(db, tmp_path, owner)
    lawyer = _lawyer(db)
    _send(db, review, lawyer)
    made = _contract(db, lawyer)
    _ingest(db, tmp_path, made, _docx(OURS), "ours.docx")
    made.owner_id = owner.id
    db.flush()
    sign_in(api, db, lawyer)
    listed = {row["id"] for row in api.get(f"{V1}/contracts?scope=legal").json()["data"]}
    assert listed == {str(sent.id), str(made.id)}
    assert str(other.id) not in listed
    for cid in listed:
        assert api.get(f"{V1}/contracts/{cid}").status_code == 200
    assert api.get(f"{V1}/contracts/summary?scope=legal").json()["data"]["total"] == 2
    sign_in(api, db, owner)
    assert api.get(f"{V1}/contracts?scope=legal").status_code == 403


# ------------------------------------------------- AM-284 / AM-285 our wording
def test_writing_our_wording_needs_the_customization_right(api, db, owner, tmp_path):
    c, _, _ = _measured(db, tmp_path, owner)
    change = _changes(api, c)["changes"][0]
    assert _changes(api, c)["can_write_wording"] is False
    r = _wording(api, c, change)
    assert r.status_code == 403 and r.json()["error"]["code"] == "FORBIDDEN"
    bad = api.post(_url(c, change["row_key"]), json=_first("write_wording"))
    assert bad.status_code == 422                     # no wording, no answer


def test_our_wording_is_decided_before_the_reply_and_written_as_our_tracked_change(
        api, db, owner, tmp_path):
    c, theirs, review = _measured(db, tmp_path, owner)
    lawyer = _lawyer(db)
    _send(db, review, lawyer)
    sign_in(api, db, lawyer)
    change = _changes(api, c)["changes"][0]
    r = _wording(api, c, change)
    assert r.status_code == 201, r.text
    body = r.json()["data"]
    assert body["waiting_for_approval"] is False
    assert body["answer"]["answer"] == "write_wording"
    assert body["answer"]["internal_note"] == SECRET    # a legal_position.view holder
    # the Legal Decision carries the wording's hash (AM-284 r2)
    ev = change["review"]["after"][0]["evaluation_ids"][0]
    decision = db.scalars(select(M.LegalDecision).where(
        M.LegalDecision.evaluation_id == uuid.UUID(ev))).one()
    assert decision.decision_type is E.DecisionType.APPROVE_CUSTOMIZATION
    assert sha256(WORDING) in decision.justification
    stored = db.scalars(select(M.ComparisonChoice).where(
        M.ComparisonChoice.row_key == change["row_key"])).one()
    assert (stored.choice, stored.wording_sha256) == ("custom", sha256(WORDING))

    prepared = api.post(REPLY.format(c.id))
    assert prepared.status_code == 201, prepared.text
    data = prepared.json()["data"]
    assert data["our_wording"] == 1 and data["open_points"] is None
    reply = api.get(f"{V1}{data['downloads']['docx']}")
    assert reply.status_code == 200
    with zipfile.ZipFile(io.BytesIO(reply.content)) as z:
        document = z.read("word/document.xml").decode()
        comments = z.read("word/comments.xml").decode()
        everything = b"".join(z.read(n) for n in z.namelist())
    assert "<w:ins " in document and "<w:del " in document       # OUR tracked change
    assert _read(reply.content) == WORDING.split("\n")
    assert NOTE in comments                            # the note to the client (r6)
    assert SECRET.encode() not in everything           # never the internal note (r3)
    trail = db.scalars(select(M.AuditEvent.after_state)).all()
    assert not any(SECRET in str(a) for a in trail)


def test_the_internal_note_key_is_omitted_without_the_position_right(
        api, db, owner, tmp_path):
    c, _, review = _measured(db, tmp_path, owner)
    lawyer = _lawyer(db)
    _send(db, review, lawyer)
    sign_in(api, db, lawyer)
    assert _wording(api, c, _changes(api, c)["changes"][0]).status_code == 201
    without_legal_position(db, owner)
    sign_in(api, db, owner)
    listed = _changes(api, c)
    assert listed["changes"][0]["answer"]["client_note"] == NOTE
    _no_key(listed, "internal_note")
    pair = {"left": str(listed["from"]["document_version_id"]),
            "right": str(listed["to"]["document_version_id"])}
    choices = api.get(f"{V1}/comparisons/choices", params=pair)   # Diff-Talk's reader
    assert choices.status_code == 200, choices.text
    assert choices.json()["data"]["choices"]
    _no_key(choices.json(), "internal_note")


# ------------------------------------------------------ AM-289 second approver
def test_wording_on_ones_own_contract_waits_for_a_second_holder(
        api, db, owner, tmp_path):
    c, _, review = _measured(db, tmp_path, owner)
    grant_role(db, owner, P.ROLE_LEGAL_DECISION_AUTHORITY)
    change = _changes(api, c)["changes"][0]
    r = _wording(api, c, change)
    assert r.status_code == 201, r.text
    assert r.json()["data"]["waiting_for_approval"] is True
    blocked = api.post(REPLY.format(c.id))
    assert blocked.status_code == 409 and "for approval" in blocked.json()["error"]["message"]

    second = _lawyer(db)
    _send(db, review, second)
    sign_in(api, db, second)
    change = _changes(api, c)["changes"][0]
    assert change["waiting_for_approval"] is True
    confirmed = _wording(api, c, change)
    assert confirmed.status_code == 201, confirmed.text
    assert confirmed.json()["data"]["waiting_for_approval"] is False
    assert api.post(REPLY.format(c.id)).status_code == 201


def test_a_review_is_never_assigned_back_to_its_creator(api, db, owner, tmp_path):
    creator = _lawyer(db)
    grant_role(db, creator, P.ROLE_USER)
    c = _contract(db, creator)
    v1 = _ingest(db, tmp_path, c, _docx(OURS), "ours.docx")
    review = _review(db, v1, [])
    c.owner_id = owner.id
    db.flush()
    sign_in(api, db, owner)
    listed = api.get(f"{V1}/reviews/{review.id}/assignments").json()["data"]
    assert str(creator.id) not in {e["user_id"] for e in listed["eligible"]}
    r = api.post(f"{V1}/reviews/{review.id}/assignments", json={"user_id": str(creator.id)})
    assert r.status_code == 422


# -------------------------------------------------------------- our standard
def _publish_clause(db, owner, code, text):
    snap = db.scalars(select(M.ConfigurationSnapshot)).first()
    cv = M.ClauseVersion(clause_key="LIAB.CAP", version=1, status="APPROVED",
                         title="Liability", body=[{"kind": "p", "text": text}],
                         realises=[code], source={"synthetic": True}, content_hash="x",
                         created_by=owner.id, approved_by=owner.id,
                         approved_at=datetime.now(UTC))
    db.add(cv)
    db.flush()
    db.add(M.TemplateVersion(template_key="T", version=1, status="PUBLISHED",
                             doc_type="MSA", layout={}, variables=[], annexures=[],
                             clauses=[{"clause_key": "LIAB.CAP", "version": 1}],
                             assets={}, source={}, content_hash="y",
                             checked_snapshot_id=snap.id, created_by=owner.id,
                             approved_by=owner.id, published_by=owner.id))
    db.flush()
    return cv


def test_use_our_standard_needs_a_published_clause_and_writes_its_words(
        api, db, owner, tmp_path):
    c, _, _ = _measured(db, tmp_path, owner)
    change = _changes(api, c)["changes"][0]
    r = api.post(_url(c, change["row_key"]), json=_first("use_standard"))
    assert r.status_code == 409 and r.json()["error"]["code"] == "NO_STANDARD_CLAUSE"
    code = change["review"]["after"][0]["requirement_code"]
    cv = _publish_clause(db, owner, code, "9. Placeholder standard clause text.")
    r = api.post(_url(c, change["row_key"]), json=_first("use_standard"))
    assert r.status_code == 201, r.text
    assert r.json()["data"]["answer"]["clause_version_id"] == str(cv.id)
    data = api.post(REPLY.format(c.id)).json()["data"]
    assert data["our_standard"] == 1
    reply = api.get(f"{V1}{data['downloads']['docx']}").content
    assert _read(reply) == ["9. Placeholder standard clause text."]


# --------------------------------------------------------- AM-290 paper first
def test_client_paper_first_rows_are_findings_and_the_reply_is_built_on_it(
        api, db, owner, tmp_path):
    c = _contract(db, owner)
    paper = _ingest(db, tmp_path, c, _docx(THEIRS, "10. Notices by email."), "theirs.docx")
    paper.doc_metadata = {"version_role": "CLIENT_MODIFIED"}
    db.flush()
    _review(db, paper, [(0, E.FindingClassification.DEVIATION, E.RuleOutcome.UNACCEPTABLE)])
    listed = _changes(api, c)
    assert listed["from"] is None and [ch["kind"] for ch in listed["changes"]] == ["THEIRS"]
    row = listed["changes"][0]
    assert row["anchor"] == {"left_key": None, "clause_version_id": None}
    r = api.post(_url(c, row["row_key"]), json=_first("keep_ours"))
    assert r.status_code == 409 and r.json()["error"]["code"] == "NOTHING_OF_OURS"

    lawyer = _lawyer(db)
    _send(db, db.scalars(select(M.Review).where(
        M.Review.document_version_id == paper.id)).one(), lawyer)
    sign_in(api, db, lawyer)
    assert _wording(api, c, row).status_code == 201
    stored = db.scalars(select(M.ComparisonChoice)).one()
    assert (stored.left_version_id, stored.left_key) == (None, None)
    prepared = api.post(REPLY.format(c.id))
    assert prepared.status_code == 201, prepared.text
    reply = api.get(f"{V1}{prepared.json()['data']['downloads']['docx']}").content
    assert _read(reply) == [*WORDING.split("\n"), "10. Notices by email."]


# ------------------------------------------------------------- AM-293 the gate
def test_an_undecided_reply_is_neither_downloaded_nor_sent(api, db, owner, tmp_path):
    c, theirs, _ = _measured(db, tmp_path, owner)
    reply = _ingest(db, tmp_path, c, _docx(OURS), "reply.docx")
    reply.doc_metadata = {"version_role": "COMPANY_DRAFT", "reply_to": str(theirs.id)}
    db.flush()
    for url in (f"/document-versions/{reply.id}/content",
                f"/document-versions/{reply.id}/reply-pdf"):
        r = api.get(f"{V1}{url}")
        assert r.status_code == 409 and r.json()["error"]["code"] == "REPLY_UNDECIDED"
        assert r.json()["error"]["reason"] == "ANALYSIS_NOT_FINISHED"
    sent = api.post(f"{V1}/document-versions/{reply.id}/mark-sent")
    assert sent.status_code == 409 and sent.json()["error"]["code"] == "REPLY_UNDECIDED"

    review = _review(db, reply, [(0, E.FindingClassification.DEVIATION,
                                  E.RuleOutcome.UNACCEPTABLE)])
    r = api.get(f"{V1}/document-versions/{reply.id}/content")
    assert r.status_code == 409 and r.json()["error"]["reason"] == "UNDECIDED_POINTS"
    (point,) = r.json()["error"]["open_points"]
    assert point["finding_id"] == str(db.scalars(select(M.Finding.id).where(
        M.Finding.review_id == review.id)).one())
    # an ordinary upload is never gated
    assert api.get(f"{V1}/document-versions/{theirs.id}/content").status_code == 200


# --------------------------------------------- AM-284 r4: the builder's sources
def test_the_builder_writes_only_wording_whose_hash_was_approved(db, owner, tmp_path):
    c = _contract(db, owner)
    ours = _ingest(db, tmp_path, c, _docx(OURS), "ours.docx")
    data = _docx(THEIRS)
    theirs = _ingest(db, tmp_path, c, data, "theirs.docx")
    from legalmind.analysis import negotiation
    key = negotiation.changes(db, c, ours, theirs, legal_position=True)["changes"][0][
        "row_key"]
    good = reply_rows(db, ours, theirs, {key: Answer("write_wording", WORDING,
                                                     sha256(WORDING))}, data)
    assert good[0].error is None
    assert [e.new_text for e in good[0].edits] == WORDING.split("\n")
    tampered = reply_rows(db, ours, theirs, {key: Answer("write_wording", WORDING + "!",
                                                         sha256(WORDING))}, data)
    assert tampered[0].error is not None and tampered[0].error.code == "INVALID_EDIT"
    kept = reply_rows(db, ours, theirs, {key: Answer("keep_ours")}, data)
    assert [e.new_text for e in kept[0].edits] == [OURS]    # our prior evidence only
