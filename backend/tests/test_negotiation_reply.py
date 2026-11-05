"""Prepare our reply — R6, `AM-251` r2 (AB-150, 2026-11-02).

The client's own DOCX with our recorded answers as tracked changes, ingested as our next
version (declared Company draft) and audited once; refused while a change is unanswered,
while an accepted holder change has no Legal Decision accepting it, and when the client
sent a PDF. Every document here is synthetic; none names a client.
"""

from __future__ import annotations

import io
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from legalmind.analysis import negotiation
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.ingestion.parsing import parse_docx
from legalmind.security import audit
from legalmind.security import permissions as P
from tests.conftest import grant_role, make_user, sign_in
from tests.test_negotiation import (  # noqa: F401 — `owner` is a fixture
    _changes,
    _contract,
    _docx,
    _first,
    _ingest,
    _mark,
    _pair,
    _review,
    _run,
    _url,
    owner,
)
from tests.test_version_comparison import V1

OURS = ["1. Fees are payable within 30 days of invoice.",
        "2. This Agreement is governed by the laws of India.",
        "3. Notices shall be given in writing to the registered office.",
        "4. The Customer's Term is one year from the Effective Date."]
THEIRS = [
    [_run("1. Fees are payable within "), _mark("del", "30", 1), _mark("ins", "60", 2),
     _run(" days of invoice.")],                                      # tracked
    "2. This Agreement is governed by the laws of Singapore.",        # silent
    # clause 3 removed, without a mark
    "4. The Customer\u2019s Term is one year from the Effective Date.",  # typography
    "5. The Customer may assign this Agreement freely."]              # added
REPLY = f"{V1}/contracts/{{}}/reply"


@pytest.fixture(autouse=True)
def published(db, owner):
    """A published (empty) configuration, so our reply is reviewed when prepared
    (`AM-251` r4) — without one its Review is missing and `AM-293` keeps it from being
    downloaded (fail closed; `test_negotiation_wording` asserts that refusal)."""
    db.add(M.ConfigurationSnapshot(snapshot_hash=uuid.uuid4().hex, created_by=owner.id,
                                   # older than any snapshot a test makes itself
                                   created_at=datetime.now(UTC) - timedelta(days=1)))
    db.flush()


def _answer(api, contract, change, answer, **body):
    seen = (change["answer"] or {}).get("version_number", 0)
    r = api.post(_url(contract, change["row_key"]),
                 json={"answer": answer, "expected_version": seen, **body})
    assert r.status_code == 201, r.text


def _negotiated(api, db, owner, tmp_path):
    c = _contract(db, owner)
    ours = _ingest(db, tmp_path, c, _docx(*OURS), "ours.docx")
    theirs = _ingest(db, tmp_path, c, _docx(*THEIRS), "theirs.docx")
    return c, ours, theirs


def _text(data: bytes) -> list[str]:
    return [s.content for s in parse_docx(data).segments]


def test_the_reply_writes_exactly_the_kept_answers(api, db, owner, tmp_path, monkeypatch):
    """Keep ours on a tracked edit, a silent edit, a deletion and an addition; accept a
    typography change. The reply reads back as ours where kept, theirs where accepted —
    and comparing it with the client's version lists exactly the kept changes."""
    monkeypatch.delenv("LEGALMIND_SOFFICE", raising=False)
    c, _, theirs = _negotiated(api, db, owner, tmp_path)
    listed = _changes(api, c)
    kinds = {(ch["kind"], ch["clause"]["number"]): ch for ch in listed["changes"]}
    assert set(kinds) == {("MODIFIED", "1"), ("MODIFIED", "2"), ("DELETED", "3"),
                          ("MODIFIED", "4"), ("ADDED", "5")}
    assert kinds[("MODIFIED", "4")]["route"] == "owner"
    for key, change in kinds.items():
        _answer(api, c, change, "accept_theirs" if key[1] == "4" else "keep_ours")

    r = api.post(REPLY.format(c.id))
    assert r.status_code == 201, r.text
    body = r.json()["data"]
    version = db.get(M.DocumentVersion, body["document_version"]["id"])
    assert version.version_number == 3 and (body["kept_ours"], body["accepted_theirs"]) \
        == (4, 1)
    assert version.doc_metadata["version_role"] == "COMPANY_DRAFT"
    assert version.doc_metadata["reply_to"] == str(theirs.id)
    assert body["document_version"]["reply"] == {"to_version_id": str(theirs.id),
                                                 "tracked": 4, "by_hand": []}

    downloaded = api.get(f"{V1}{body['downloads']['docx']}")
    assert downloaded.status_code == 200
    reply = downloaded.content
    assert _text(reply) == [*OURS[:3], THEIRS[2]]
    # nothing else: the reply against the client's version is the kept changes, once
    back = negotiation.changes(db, c, theirs, version, legal_position=True)["changes"]
    assert sorted((ch["kind"], ch["clause"]["number"]) for ch in back) == [
        ("ADDED", "3"), ("DELETED", "5"), ("MODIFIED", "1"), ("MODIFIED", "2")]
    # every one of them is OUR tracked change (the client's own marks stay beside them)
    assert all(ch["tracked"] for ch in back)
    assert db.scalar(select(func.count()).select_from(M.AuditEvent).where(
        M.AuditEvent.action == audit.DOCUMENT_REPLY_PREPARED,
        M.AuditEvent.entity_id == c.id)) == 1

    # no LibreOffice here: the client PDF is a plain refusal, never a PyMuPDF copy
    pdf = api.get(f"{V1}{body['downloads']['pdf']}")
    assert pdf.status_code == 503 and pdf.json()["error"]["code"] == "PDF_NOT_MADE"
    # the latest version is ours now: nothing to reply to
    assert api.post(REPLY.format(c.id)).status_code == 409
    # and that round is closed: its answers are the record the reply was written from
    after_reply = api.get(f"{V1}/contracts/{c.id}/changes",
                          params={"from_version": 1, "to_version": 2}).json()["data"]
    assert after_reply["replied_in"] == 3 and after_reply["can_answer"] is False
    assert after_reply["can_send"] is True          # Mark sent outlives the round
    late = api.post(_url(c, kinds[("MODIFIED", "4")]["row_key"]) + "?from_version=1&to_version=2",
                    json={"answer": "keep_ours", "expected_version": 1})
    assert late.status_code == 409, late.text


def test_a_reply_is_refused_while_a_change_is_unanswered(api, db, owner, tmp_path):
    c, _, _ = _negotiated(api, db, owner, tmp_path)
    first = _changes(api, c)["changes"][0]
    _answer(api, c, first, "keep_ours")
    r = api.post(REPLY.format(c.id))
    assert r.status_code == 409
    error = r.json()["error"]
    assert error["code"] == "REPLY_NOT_READY" and "4 changes not answered" in error["message"]
    assert db.scalar(select(func.count()).select_from(M.DocumentVersion)
                     .where(M.DocumentVersion.contract_id == c.id)) == 2


def test_a_client_pdf_cannot_carry_our_tracked_changes(api, db, owner):
    c = _contract(db, owner)
    _pair(db, c, "9. Liability is capped.", "9. Liability is uncapped.")
    _answer(api, c, _changes(api, c)["changes"][0], "keep_ours")
    r = api.post(REPLY.format(c.id))
    assert r.status_code == 409 and r.json()["error"]["code"] == "REPLY_NEEDS_WORD_FILE"


def test_a_holder_change_is_accepted_only_under_a_legal_decision(api, db, owner, tmp_path):
    """`AM-250` r2: accepting a measured change needs a holder's Legal Decision; once it
    accepts every Evaluation the answer may say "accept theirs", and a later decision
    that no longer accepts it stops the reply."""
    c = _contract(db, owner)
    _ingest(db, tmp_path, c, _docx("9. Liability is capped at 12 months of fees."), "o.docx")
    theirs = _ingest(db, tmp_path, c, _docx("9. Liability is capped at 3 months of fees."),
                     "t.docx")
    _review(db, theirs, [(0, E.FindingClassification.DEVIATION, E.RuleOutcome.UNACCEPTABLE)])
    change = _changes(api, c)["changes"][0]
    assert change["route"] == "holder" and change["holder_accepted"] is False
    r = api.post(_url(c, change["row_key"]), json=_first("accept_theirs"))
    assert r.status_code == 403 and r.json()["error"]["code"] == "LEGAL_DECISION_REQUIRED"

    evaluation = db.get(M.Evaluation, change["review"]["after"][0]["evaluation_ids"][0])
    # AM-289 (reversing AM-170 O2): the owner's own decision would wait for a second
    # person, so the holder deciding here is someone else
    lawyer = make_user(db)
    db.add(M.LegalDecision(finding_id=evaluation.finding_id, evaluation_id=evaluation.id,
                           decision_type=E.DecisionType.ACCEPT_DEVIATION,
                           justification="accepted for this deal", decided_by=lawyer.id,
                           version_number=1))
    db.flush()
    assert _changes(api, c)["changes"][0]["holder_accepted"] is True
    _answer(api, c, change, "accept_theirs")

    db.add(M.LegalDecision(finding_id=evaluation.finding_id, evaluation_id=evaluation.id,
                           decision_type=E.DecisionType.REQUEST_CLARIFICATION,
                           justification="asked again", decided_by=lawyer.id,
                           version_number=2))
    db.flush()
    r = api.post(REPLY.format(c.id))
    assert r.status_code == 409 and "needs a Legal Decision" in r.json()["error"]["message"]


SOFFICE = os.environ.get(
    "LEGALMIND_SOFFICE",
    "/root/legalmind-clm-local/lo/root/opt/libreoffice26.2/program/soffice")


@pytest.mark.skipif(not os.path.exists(SOFFICE), reason="LibreOffice not installed here")
def test_libreoffice_renders_the_reply_pdf(api, db, owner, tmp_path, monkeypatch):
    c, _, _ = _negotiated(api, db, owner, tmp_path)
    for change in _changes(api, c)["changes"]:
        _answer(api, c, change, "accept_theirs" if change["route"] == "owner"
                else "keep_ours")
    monkeypatch.setenv("LEGALMIND_SOFFICE", SOFFICE)   # inline: made with the reply
    body = api.post(REPLY.format(c.id)).json()["data"]
    pdf = api.get(f"{V1}{body['downloads']['pdf']}")
    assert pdf.status_code == 200
    import pymupdf
    text = pymupdf.open(stream=pdf.content, filetype="pdf")[0].get_text()
    assert "Reading copy" not in text and "India" in text     # the clean copy


def _table_docx(intro: str, *rows: tuple[str, str]) -> bytes:
    import io

    import docx
    d = docx.Document()
    d.add_paragraph(intro)
    table = d.add_table(rows=len(rows), cols=2)
    for r, (a, b) in zip(table.rows, rows, strict=True):
        r.cells[0].paragraphs[0].text, r.cells[1].paragraphs[0].text = a, b
    out = io.BytesIO()
    d.save(out)
    return out.getvalue()


def test_a_kept_table_is_restored_cell_by_cell(api, db, owner, tmp_path):
    """A table row is one evidence row; keeping ours rewrites only the changed cell."""
    c = _contract(db, owner)
    _ingest(db, tmp_path, c, _table_docx("1. Fees.", ("Hosting", "30 days"),
                                         ("Support", "15 days")), "o.docx")
    _ingest(db, tmp_path, c, _table_docx("1. Fees.", ("Hosting", "60 days"),
                                         ("Support", "15 days")), "t.docx")
    for change in _changes(api, c)["changes"]:
        _answer(api, c, change, "keep_ours")
    body = api.post(REPLY.format(c.id)).json()["data"]
    reply = api.get(f"{V1}{body['downloads']['docx']}").content
    assert _text(reply) == ["1. Fees.", "| Hosting | 30 days |\n| Support | 15 days |"]


# ------------------------------------------------------------- AB-151 review fixes
def _decide(db, evaluation, kind, by, n):
    db.add(M.LegalDecision(finding_id=evaluation.finding_id, evaluation_id=evaluation.id,
                           decision_type=kind, justification="decided", decided_by=by,
                           version_number=n))
    db.flush()


def test_one_signature_of_two_accepts_nothing(api, db, owner, tmp_path):
    """`AM-281` r3: where the standard requires a second person, one ACCEPT_DEVIATION
    is not an effective decision — the answer is refused and the reply blocked until a
    second, different holder signs the same."""
    from tests.conftest import require_second_person

    c = _contract(db, owner)
    _ingest(db, tmp_path, c, _docx("9. Liability is capped at 12 months of fees."), "o.docx")
    theirs = _ingest(db, tmp_path, c, _docx("9. Liability is capped at 3 months of fees."),
                     "t.docx")
    review = _review(db, theirs, [(0, E.FindingClassification.DEVIATION,
                                   E.RuleOutcome.UNACCEPTABLE)])
    change = _changes(api, c)["changes"][0]
    evaluation = db.get(M.Evaluation, change["review"]["after"][0]["evaluation_ids"][0])
    require_second_person(db, review, db.get(M.Finding, evaluation.finding_id))
    _decide(db, evaluation, E.DecisionType.ACCEPT_DEVIATION, owner.id, 1)
    assert _changes(api, c)["changes"][0]["holder_accepted"] is False
    r = api.post(_url(c, change["row_key"]), json=_first("accept_theirs"))
    assert r.status_code == 403 and r.json()["error"]["code"] == "LEGAL_DECISION_REQUIRED"

    second = make_user(db)
    _decide(db, evaluation, E.DecisionType.ACCEPT_DEVIATION, second.id, 2)
    assert _changes(api, c)["changes"][0]["holder_accepted"] is True
    _answer(api, c, change, "accept_theirs")
    _decide(db, evaluation, E.DecisionType.REJECT, second.id, 3)    # one signature again
    r = api.post(REPLY.format(c.id))
    assert r.status_code == 409 and "needs a Legal Decision" in r.json()["error"]["message"]


def test_a_holder_answers_a_change_no_standard_measures(api, db, owner, tmp_path):
    """`AM-281`: on an unmeasured holder change the owner may not accept; a holder of
    `legal.decision` who reads the contract may — reason required, audited — and the
    reply honours it. It is an answer, never a Legal Decision."""
    c, _, _ = _negotiated(api, db, owner, tmp_path)
    team = M.Department(code=f"T{uuid.uuid4().hex[:6]}", name="Team")
    db.add(team)
    db.flush()
    holder = make_user(db)
    grant_role(db, holder, P.ROLE_DEPARTMENT_LEAD)
    grant_role(db, holder, P.ROLE_LEGAL_DECISION_AUTHORITY)
    owner.department_id = holder.department_id = team.id
    db.flush()
    changes = {(ch["kind"], ch["clause"]["number"]): ch for ch in _changes(api, c)["changes"]}
    added = changes[("ADDED", "5")]
    assert added["route"] == "holder" and added["unmeasured"]
    r = api.post(_url(c, added["row_key"]), json=_first("accept_theirs"))
    assert r.status_code == 403                                      # the owner

    sign_in(api, db, holder)
    r = api.post(_url(c, added["row_key"]), json=_first("accept_theirs"))
    assert r.status_code == 422                                      # no reason
    r = api.post(_url(c, added["row_key"]),
                 json=_first("accept_theirs", reason="assignment is fine here"))
    assert r.status_code == 201, r.text
    assert db.scalar(select(func.count()).select_from(M.AuditEvent).where(
        M.AuditEvent.action == audit.NEGOTIATION_HOLDER_ANSWERED,
        M.AuditEvent.actor_id == holder.id)) == 1
    assert db.scalar(select(func.count()).select_from(M.LegalDecision)) == 0

    sign_in(api, db, owner)
    for key, change in changes.items():
        if key != ("ADDED", "5"):
            _answer(api, c, change, "accept_theirs" if key[1] == "4" else "keep_ours")
    assert _changes(api, c)["changes"][-1]["holder_accepted"] is True
    body = api.post(REPLY.format(c.id)).json()["data"]
    reply = api.get(f"{V1}{body['downloads']['docx']}").content
    assert _text(reply) == [*OURS[:3], THEIRS[2], THEIRS[3]]


def test_a_table_cell_reading_the_same_words_is_never_the_paragraph(
        api, db, owner, tmp_path):
    """The rank is over the body's NON-table paragraphs: a cell with the same words
    before the clause is not the paragraph rewritten."""
    def doc(last: str) -> bytes:
        import docx
        d = docx.Document()
        d.add_paragraph("1. Fees.")
        cells = d.add_table(rows=1, cols=2).rows[0].cells
        cells[0].paragraphs[0].text, cells[1].paragraphs[0].text = "Fees are due.", "Monthly"
        d.add_paragraph(last)
        buf = io.BytesIO()
        d.save(buf)
        return buf.getvalue()

    c = _contract(db, owner)
    _ingest(db, tmp_path, c, doc("Fees are due within 30 days."), "o.docx")
    _ingest(db, tmp_path, c, doc("Fees are due."), "t.docx")
    for change in _changes(api, c)["changes"]:
        _answer(api, c, change, "keep_ours")
    r = api.post(REPLY.format(c.id))
    assert r.status_code == 201, r.text
    reply = api.get(f"{V1}{r.json()['data']['downloads']['docx']}").content
    assert _text(reply) == ["1. Fees.", "| Fees are due. | Monthly |",
                            "Fees are due within 30 days."]


def _two_tables(first: str, third: str) -> bytes:
    import docx
    d = docx.Document()
    for heading, cell in (("1. Hosting.", first), ("2. Support.", "60 days")):
        d.add_paragraph(heading)
        cells = d.add_table(rows=1, cols=2).rows[0].cells
        cells[0].paragraphs[0].text, cells[1].paragraphs[0].text = "Credit", cell
    d.add_paragraph(third)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def test_an_answer_that_cannot_be_placed_is_listed_then_left_to_a_person(
        api, db, owner, tmp_path):
    """Two tables now read the same, so which one to restore is never guessed
    (ANCHOR_AMBIGUOUS). The 409 lists every such change; naming exactly that list
    prepares the reply with every other answer written and a Word comment there."""
    import zipfile

    c = _contract(db, owner)
    _ingest(db, tmp_path, c, _two_tables("30 days", "3. Notices in writing."), "o.docx")
    theirs = _ingest(db, tmp_path, c, _two_tables("60 days", "3. Notices by email."),
                     "t.docx")
    for change in _changes(api, c)["changes"]:
        _answer(api, c, change, "keep_ours")
    r = api.post(REPLY.format(c.id))
    assert r.status_code == 409, r.text
    error = r.json()["error"]
    assert error["code"] == "REPLY_NOT_APPLIED"
    [manual] = error["manual_rows"]
    assert manual["clause"] == "clause 1" and "ANCHOR_AMBIGUOUS" in manual["reason"]
    assert api.post(REPLY.format(c.id), json={"manual_rows": ["N|x"]}).status_code == 409

    r = api.post(REPLY.format(c.id), json={"manual_rows": [manual["row_key"]]})
    assert r.status_code == 201, r.text
    body = r.json()["data"]
    assert [m["row_key"] for m in body["manual_rows"]] == [manual["row_key"]]
    assert body["manual_rows"][0]["commented"] is True
    reply = api.get(f"{V1}{body['downloads']['docx']}").content
    assert _text(reply) == ["1. Hosting.", "| Credit | 60 days |", "2. Support.",
                            "| Credit | 60 days |", "3. Notices in writing."]
    with zipfile.ZipFile(io.BytesIO(reply)) as package:
        comments = package.read("word/comments.xml").decode()
    assert "LeapSwitch: restore our wording here by hand — clause 1" in comments
    event = db.scalars(select(M.AuditEvent).where(
        M.AuditEvent.action == audit.DOCUMENT_REPLY_PREPARED,
        M.AuditEvent.entity_id == c.id)).one()
    assert event.after_state["manual_rows"] == [
        {"row_key": manual["row_key"], "clause": "clause 1"}]
    version = db.get(M.DocumentVersion, body["document_version"]["id"])
    assert version.doc_metadata["reply_to"] == str(theirs.id)


def _all_kept(api, c):
    for change in _changes(api, c)["changes"]:
        _answer(api, c, change, "keep_ours")


def test_the_reply_is_reviewed_like_any_upload(api, db, owner, tmp_path):
    """`AM-251` r4: preparing the reply opens a Review of it on the newest published
    snapshot and runs the analysis through the same dispatch as an upload's — so the
    reply's Document tab never says "not analysed yet"."""
    c, _, _ = _negotiated(api, db, owner, tmp_path)
    snap = M.ConfigurationSnapshot(snapshot_hash=uuid.uuid4().hex, created_by=owner.id)
    db.add(snap)
    db.flush()
    _all_kept(api, c)
    r = api.post(REPLY.format(c.id))
    assert r.status_code == 201, r.text
    body = r.json()["data"]
    review = db.get(M.Review, uuid.UUID(body["review_id"]))
    assert review.document_version_id == uuid.UUID(body["document_version"]["id"])
    assert review.configuration_snapshot_id == snap.id
    assert review.created_by == owner.id
    assert review.status is not E.ReviewStatus.DRAFT          # analysed, inline here
    # the upload chain afterwards finds the same Review (43.28), never a second one
    again = api.post(f"{V1}/reviews", json={"document_version_id": body["document_version"]["id"],
                                             "configuration_snapshot_id": str(snap.id)})
    assert again.json()["data"]["id"] == body["review_id"]


def test_a_queued_reply_analysis_is_sent_only_after_the_commit(db, owner, monkeypatch):
    """With a broker, the reply's Review is new in the request's own transaction: the
    message waits for the commit, or a worker would drop it as review_not_found."""
    from legalmind.worker import dispatch, tasks
    from tests.conftest import make_review_for

    review = make_review_for(db, owner)
    sent: list[dict] = []
    monkeypatch.setattr(dispatch, "configure_broker", lambda: object())
    monkeypatch.setattr(dispatch, "assert_analysable", lambda *_, **__: None)
    monkeypatch.setattr(dispatch, "_off_loop", lambda fn: fn())
    monkeypatch.setattr(tasks.analyse_review, "apply_async",
                        lambda **kw: sent.append(kw["kwargs"]))
    out = dispatch.dispatch_analysis(db, review, after_commit=True)
    assert out.mode is dispatch.DispatchMode.QUEUED and sent == []
    db.dispatch.after_commit(db)
    assert [m["review_id"] for m in sent] == [str(review.id)]
