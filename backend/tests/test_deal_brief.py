"""Batch 3+4 "deal brief" (AB-218): what Legal told the client, the one-minute
brief, one label per change row, and one notice when Legal has answered every change.

Every document is synthetic and names no client. A recorded position here is TEST text
written by the test, never a position of ours (rule 21): it is asserted only for where it
goes and where it never goes.
"""

from __future__ import annotations

import io
import json
import uuid
import zipfile

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from legalmind import notifications
from legalmind.analysis import negotiation
from legalmind.api.angles import WHOLE_CONTRACT, review_angles
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.security import permissions as P
from legalmind.workflow.review_progress import review_progress
from tests.conftest import (
    bespoke_role,
    grant,
    grant_role,
    make_evaluation,
    make_finding,
    make_user,
    sign_in,
)
from tests.test_negotiation import (  # noqa: F401 — `owner` is a fixture
    _changes,
    _contract,
    _docx,
    _ingest,
    _review,
    _url,
    owner,
)
from tests.test_negotiation_reply import OURS, THEIRS, published  # noqa: F401
from tests.test_negotiation_wording import _lawyer, _send
from tests.test_version_comparison import V1

#: TEST words only — what the test records as "what we told them"
TOLD = "Test note: we offered the client a mutual cap and a thirty day exit qq7z"
NOTE = "Test email pasted by sales: mutual cap, thirty day exit"


def _deal(api, db, owner, tmp_path):
    """Ours, then the client's (four Legal changes and one owner change), a Review on
    theirs with one point, sent to a lawyer with a Note for Legal."""
    c = _contract(db, owner)
    _ingest(db, tmp_path, c, _docx(*OURS), "ours.docx")
    theirs = _ingest(db, tmp_path, c, _docx(*THEIRS), "theirs.docx")
    review = _review(db, theirs, [(0, E.FindingClassification.DEVIATION,
                                   E.RuleOutcome.UNACCEPTABLE)])
    review.status = E.ReviewStatus.LEGAL_REVIEW
    lawyer = _lawyer(db)
    _send(db, review, lawyer)
    db.execute(select(M.ReviewAssignment).where(
        M.ReviewAssignment.review_id == review.id)).scalar_one().note = NOTE
    db.flush()
    return c, theirs, review, lawyer


def _get(api, path):
    r = api.get(f"{V1}{path}")
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _record(api, c, ties=None, key=None, expected=0, **body):
    url = f"{V1}/contracts/{c.id}/positions" + (f"/{key}" if key else "")
    return api.post(url, json={"text": TOLD, "ties": ties or {},
                               "expected_version": expected, **body})


def _holder_rows(listed):
    return [ch for ch in listed["changes"] if ch["route"] == negotiation.HOLDER]


# ------------------------------------------------------------------ check 1
def _routing(listed: dict) -> str:
    """Everything a position must never move, as bytes: each row's route, reason,
    effect, measured word, answer and automatic flag, and the list's own tallies."""
    return json.dumps({"summary": listed["summary"], "rows": [
        [c["row_key"], c["route"], c["route_reason"], c["effect_for_us"], c.get("measured"),
         c["answer"], c.get("holder_accepted"), c.get("waiting_for_approval")]
        for c in listed["changes"]]}, sort_keys=True, default=str)


def test_positions_never_move_a_route_an_effect_an_answer_or_an_automatic_acceptance(
        api, db, owner, tmp_path, monkeypatch):
    monkeypatch.setattr(negotiation, "auto_rule", lambda db, review: True)
    c, theirs, review, lawyer = _deal(api, db, owner, tmp_path)
    before_v = negotiation.our_previous(list(db.execute(select(M.DocumentVersion).where(
        M.DocumentVersion.contract_id == c.id)).scalars()), theirs)

    def snapshot():
        raw = negotiation.changes(db, c, before_v, theirs, legal_position=True)
        sign_in(api, db, lawyer)
        as_lawyer = _changes(api, c)
        sign_in(api, db, owner)
        as_owner = _changes(api, c)
        return (json.dumps(raw, sort_keys=True, default=str), _routing(as_lawyer),
                _routing(as_owner), _get(api, f"/contracts/{c.id}")["counts"])

    first = snapshot()
    assert json.loads(first[1])["summary"]["auto_accepted"] == 1     # the typography row
    sign_in(api, db, lawyer)
    rows = _holder_rows(_changes(api, c))
    assert _record(api, c, {rows[0]["row_key"]: "AS_TOLD",
                            rows[1]["row_key"]: "BEYOND"}).status_code == 201
    second = _record(api, c, {rows[2]["row_key"]: "BEYOND"})
    assert second.status_code == 201
    assert snapshot() == first                                  # byte-identical
    # the label is there for Legal, and only for Legal
    sign_in(api, db, lawyer)
    told = {ch["row_key"]: ch.get("told", {}).get("tie") for ch in _changes(api, c)["changes"]}
    assert [told[r["row_key"]] for r in rows] == ["AS_TOLD", "BEYOND", "BEYOND", None]
    sign_in(api, db, owner)
    assert all("told" not in ch for ch in _changes(api, c)["changes"])


# ------------------------------------------------------------------ check 5
def test_the_brief_says_the_same_numbers_as_deal_counts_and_review_progress(
        api, db, owner, tmp_path):
    c, theirs, review, lawyer = _deal(api, db, owner, tmp_path)
    sign_in(api, db, lawyer)
    rows = _holder_rows(_changes(api, c))
    assert _record(api, c, {rows[0]["row_key"]: "BEYOND",
                            rows[1]["row_key"]: "AS_TOLD"}).status_code == 201
    for reader in (lawyer, owner):
        sign_in(api, db, reader)
        counts = _get(api, f"/contracts/{c.id}")["counts"]
        brief = _get(api, f"/contracts/{c.id}/brief")
        assert brief["counts"] == counts
        assert counts["points_open"] == review_progress(db, review)["to_decide"] == 1
        assert (counts["changes_total"], counts["changes_left_legal"]) == (5, 4)
    sign_in(api, db, lawyer)
    legal = _get(api, f"/contracts/{c.id}/brief")["legal"]
    assert [b["row_key"] for b in legal["beyond"]] == [rows[0]["row_key"]]
    assert (legal["as_told"], legal["not_discussed"]) == (1, 2)
    assert len(legal["beyond"]) + legal["as_told"] + legal["not_discussed"] == 4
    assert legal["note"] == NOTE and legal["can_record"] is True


def test_the_sales_brief_reads_the_client_asks_and_never_legals_part(
        api, db, owner, tmp_path):
    c, theirs, review, lawyer = _deal(api, db, owner, tmp_path)
    sign_in(api, db, lawyer)
    assert _record(api, c, told_on="2026-11-18").status_code == 201
    sign_in(api, db, owner)
    brief = _get(api, f"/contracts/{c.id}/brief")
    assert "legal" not in brief
    # what we told them: the words and the day, nothing else (no key, no ties)
    assert brief["told"] == [{"text": TOLD, "told_on": "2026-11-18"}]
    # one line per clause group the client changed, in contract order; the formatting
    # row is not an ask; each quotes the client's own words, no clause number in them
    assert [a["clause"] for a in brief["asks"]] == ["1", "2", "3", "5"]
    assert brief["asks"][0]["quote"].startswith("Fees are payable within 60 days")
    assert brief["asks"][2]["removed"] is True and brief["asks_more"] == 0
    words = json.dumps({k: brief[k] for k in ("asks", "told")})
    import re
    assert not re.search(r"§|[A-Z]{2,}[-_][A-Z0-9_]|requirement|evaluat|deviation|"
                         r"classification|finding", words)


def test_a_reader_without_positions_gets_no_told_key(api, db, tmp_path):
    """LEGAL-02: omitted, never nulled — a reader without `legal_position.view`."""
    reader = make_user(db)
    grant(db, reader, bespoke_role(db, f"NOPOS_{reader.id.hex[:6]}",
                                   [P.CONTRACT_VIEW, P.DOCUMENT_VIEW, P.REVIEW_VIEW]))
    c = _contract(db, reader)
    _ingest(db, tmp_path, c, _docx(*OURS), "ours.docx")
    _ingest(db, tmp_path, c, _docx(*THEIRS), "theirs.docx")
    db.add(M.DealPosition(contract_id=c.id, position_key="k", version_number=1,
                          text=TOLD, ties={}, recorded_by=reader.id))
    db.flush()
    sign_in(api, db, reader)
    brief = _get(api, f"/contracts/{c.id}/brief")
    assert "told" not in brief and "legal" not in brief and brief["asks"]
    assert "qq7z" not in json.dumps(brief)


# ------------------------------------------------------------------ check 3
def test_only_legal_records_positions(api, db, owner, tmp_path):
    c, theirs, review, lawyer = _deal(api, db, owner, tmp_path)
    other = _contract(db, owner)                       # never sent to the lawyer
    sign_in(api, db, owner)
    assert _record(api, c).status_code == 403          # the deal owner: never
    sign_in(api, db, lawyer)
    made = _record(api, c)
    assert made.status_code == 201, made.text
    key = made.json()["data"]["position_key"]
    sign_in(api, db, owner)
    assert _record(api, c, key=key, expected=1).status_code == 403
    sign_in(api, db, lawyer)
    hidden, absent = _record(api, other), api.post(
        f"{V1}/contracts/{uuid.uuid4()}/positions", json={"text": TOLD})
    assert hidden.status_code == absent.status_code == 404
    strip = lambda r: {k: v for k, v in r.json()["error"].items() if k != "request_id"}  # noqa: E731
    assert strip(hidden) == strip(absent)
    stranger = make_user(db)
    grant_role(db, stranger, P.ROLE_USER)
    sign_in(api, db, stranger)
    hidden = api.get(f"{V1}/contracts/{c.id}/brief")
    absent = api.get(f"{V1}/contracts/{uuid.uuid4()}/brief")
    assert hidden.status_code == absent.status_code == 404
    assert strip(hidden) == strip(absent)


def test_a_position_is_versioned_and_never_deleted(api, db, owner, tmp_path):
    c, theirs, review, lawyer = _deal(api, db, owner, tmp_path)
    sign_in(api, db, lawyer)
    listed = _changes(api, c)
    rows = _holder_rows(listed)
    made = _record(api, c, {rows[0]["row_key"]: "AS_TOLD"}).json()["data"]
    key = made["position_key"]
    assert made["version_number"] == 1 and made["recorded_by"]
    again = _record(api, c, {rows[0]["row_key"]: "BEYOND"}, key=key, expected=1)
    assert again.status_code == 201 and again.json()["data"]["version_number"] == 2
    assert _record(api, c, key=key, expected=1).status_code == 409        # stale
    # a row is tied to one position at a time; only Legal's rows are tied
    assert _record(api, c, {rows[0]["row_key"]: "AS_TOLD"}).status_code == 409
    owner_row = next(ch for ch in listed["changes"] if ch["route"] != negotiation.HOLDER)
    assert _record(api, c, {owner_row["row_key"]: "AS_TOLD"}).status_code == 422
    gone = _record(api, c, key=key, expected=2, withdrawn=True)
    assert gone.status_code == 201 and gone.json()["data"]["version_number"] == 3
    assert _get(api, f"/contracts/{c.id}/brief")["told"] == []
    assert all("told" not in ch for ch in _changes(api, c)["changes"])
    assert db.scalar(select(func.count()).select_from(M.DealPosition)) == 3
    with pytest.raises(DBAPIError), db.begin_nested():
        db.execute(text("UPDATE deal_positions SET text = 'x'"))
    with pytest.raises(DBAPIError), db.begin_nested():
        db.execute(text("DELETE FROM deal_positions"))


# ------------------------------------------------------------------ check 9
def _told_owner(db, c) -> int:
    return db.scalar(select(func.count()).select_from(M.Notification).where(
        M.Notification.contract_id == c.id,
        M.Notification.kind == notifications.LEGAL_ANSWERED_ALL))


def _open_point(db, review):
    """A second point on the client's version that no change row carries (a clause the
    standard finds missing): only a decision on the Points tab closes it."""
    req = M.Requirement(code=f"TEST-{uuid.uuid4().hex[:6]}", status=E.ConfigStatus.ACTIVE)
    db.add(req)
    db.flush()
    rv = M.RequirementVersion(requirement_id=req.id, version_number=1, name="Test point",
                              evaluator_type=E.EvaluatorType.PRESENCE,
                              created_by=review.created_by)
    db.add(rv)
    db.flush()
    f = make_finding(db, review, rv, classification=E.FindingClassification.MISSING)
    ev = make_evaluation(db, f, classification=E.FindingClassification.MISSING,
                         rule_outcome=E.RuleOutcome.UNACCEPTABLE)
    ev.result = {**ev.result, "evaluated_facts": {"mapping_state": "CONFIRMED"}}
    db.flush()
    return ev


def _decide_point(api, ev):
    r = api.post(f"{V1}/evaluations/{ev.id}/decisions", json={
        "decision_type": "REQUIRE_COMPANY_STANDARD", "justification": "Test decision",
        "expected_version": 0})
    assert r.status_code == 201, r.text


def _answer_all(api, db, c, before_each=None):
    for change in _holder_rows(_changes(api, c)):
        if before_each:
            before_each()
        r = api.post(_url(c, change["row_key"]),
                     json={"answer": "keep_ours", "expected_version": 0})
        assert r.status_code == 201, r.text


def test_the_owner_is_told_once_when_legal_has_answered_every_change(
        api, db, owner, tmp_path):
    """No point beside the changes: the last answer unblocks the reply — one notice."""
    c, theirs, review, lawyer = _deal(api, db, owner, tmp_path)
    sign_in(api, db, lawyer)
    _answer_all(api, db, c, before_each=lambda: _no_notice_yet(db, c))     # none per row
    assert _told_owner(db, c) == 1
    note = db.execute(select(M.Notification).where(
        M.Notification.kind == notifications.LEGAL_ANSWERED_ALL)).scalar_one()
    assert note.user_id == owner.id and note.link == f"/contracts/{c.id}/changes"
    sign_in(api, db, owner)
    [said] = [n for n in _get(api, "/notifications")["items"]
              if n["kind"] == notifications.LEGAL_ANSWERED_ALL]
    assert said["sentence"] == ("Legal has answered every change on Negotiated MSA. "
                                "Your turn: send our reply.")
    # a change answered again (still nothing left), read or unread: never twice
    note.read_at = note.created_at
    db.flush()
    sign_in(api, db, lawyer)
    last = _holder_rows(_changes(api, c))[-1]
    assert api.post(_url(c, last["row_key"]), json={
        "answer": "keep_ours", "expected_version": 1, "reason": "again"}).status_code == 201
    assert _told_owner(db, c) == 1
    assert notifications.legal_answered_all(db, c, theirs.created_at,
                                            actor_id=lawyer.id) == 0


def _no_notice_yet(db, c):
    assert _told_owner(db, c) == 0


def test_changes_first_then_the_last_point_sends_exactly_one_notice(
        api, db, owner, tmp_path):
    """(a) The last change answered while a point is open: no notice — the reply is still
    blocked. Deciding the last point unblocks it: exactly one."""
    c, theirs, review, lawyer = _deal(api, db, owner, tmp_path)
    ev = _open_point(db, review)
    sign_in(api, db, lawyer)
    _answer_all(api, db, c, before_each=lambda: _no_notice_yet(db, c))
    counts = _get(api, f"/contracts/{c.id}")["counts"]
    assert counts["changes_left_legal"] == 0 and counts["points_open"] == 1
    assert _told_owner(db, c) == 0
    _decide_point(api, ev)
    assert _get(api, f"/contracts/{c.id}")["counts"]["points_open"] == 0
    assert _told_owner(db, c) == 1


def test_the_last_point_first_then_the_last_change_sends_exactly_one_notice(
        api, db, owner, tmp_path):
    """(b) The point decided while changes wait for Legal: no notice; the last change
    answered: exactly one; (c) never one per row or per point."""
    c, theirs, review, lawyer = _deal(api, db, owner, tmp_path)
    ev = _open_point(db, review)
    sign_in(api, db, lawyer)
    _decide_point(api, ev)
    assert _told_owner(db, c) == 0
    _answer_all(api, db, c, before_each=lambda: _no_notice_yet(db, c))
    assert _told_owner(db, c) == 1


# ------------------------------------------------------------------ check 2
def _xml_text(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return " ".join(z.read(n).decode("utf-8", "ignore") for n in z.namelist())


def test_what_we_told_them_never_reaches_the_reply_its_pdf_or_an_export(
        api, db, owner, tmp_path, published, monkeypatch):
    import shutil
    c, theirs, review, lawyer = _deal(api, db, owner, tmp_path)
    sign_in(api, db, lawyer)
    listed = _changes(api, c)
    assert _record(api, c, {_holder_rows(listed)[0]["row_key"]: "AS_TOLD"},
                   told_on="2026-11-18").status_code == 201
    for change in listed["changes"]:
        who = lawyer if change["route"] == negotiation.HOLDER else owner
        sign_in(api, db, who)
        r = api.post(_url(c, change["row_key"]), json={
            "answer": "keep_ours", "expected_version":
            (change["answer"] or {}).get("version_number", 0)})
        assert r.status_code == 201, r.text
    sign_in(api, db, owner)
    if shutil.which("soffice"):
        monkeypatch.setenv("LEGALMIND_SOFFICE", shutil.which("soffice") or "")
    made = api.post(f"{V1}/contracts/{c.id}/reply")
    assert made.status_code == 201, made.text
    body = made.json()["data"]
    docx_bytes = api.get(f"{V1}{body['downloads']['docx']}").content
    assert "qq7z" not in _xml_text(docx_bytes) and TOLD not in _xml_text(docx_bytes)
    files = {"reply.docx": docx_bytes}
    pdf = api.get(f"{V1}{body['downloads']['pdf']}")
    if pdf.status_code == 200:
        files["reply.pdf"] = pdf.content
    for fmt in ("docx", "pdf"):
        exported = api.post(f"{V1}/reviews/{review.id}/export", json={"format": fmt})
        assert exported.status_code == 200, exported.text
        files[f"export.{fmt}"] = exported.content
    table = api.post(f"{V1}/contracts/{c.id}/changes/review-table/export")
    assert table.status_code == 200
    files["review-table.docx"] = table.content
    import fitz
    for name, data in files.items():
        if name.endswith(".pdf"):
            with fitz.open(stream=data, filetype="pdf") as doc:
                readable = "".join(page.get_text() for page in doc)
            assert readable.strip(), name                  # the text was read
        else:
            readable = _xml_text(data)
        assert "qq7z" not in readable, name
    # the control: the words are recorded and Legal reads them on the brief
    sign_in(api, db, lawyer)
    assert "qq7z" in json.dumps(_get(api, f"/contracts/{c.id}/brief")["told"])
    print("checked:", sorted(files), "reply pdf status", pdf.status_code)


# ------------------------------------------------------------------ check 7
def test_a_point_no_clause_holds_is_placed_on_the_whole_contract(api, db, owner, tmp_path):
    """Round 4 (lead): a point's place is a clause only when its mapping is CONFIRMED;
    otherwise "Whole contract" — in angles, the case, the brief and the review export
    (never "§N") — with its candidate clause numbers kept for Legal's "Possibly in"."""
    c, theirs, review, lawyer = _deal(api, db, owner, tmp_path)
    finding = db.execute(select(M.Finding).where(M.Finding.review_id == review.id)
                         ).scalar_one()
    ev = db.execute(select(M.Evaluation).where(M.Evaluation.finding_id == finding.id)
                    ).scalar_one()

    def placed(state):
        ev.result = {**ev.result, "evaluated_facts": {"mapping_state": state}}
        db.flush()
        [item] = review_angles(db, review, legal_position=True,
                               legal_review=True)["legal"]["items"]
        return item["where"], item["case"]["contract"]

    # nothing found at all: whole contract, no candidates
    assert placed("UNRESOLVED") == (WHOLE_CONTRACT, {"whole": True})
    # two candidate clauses (unranked): still the whole contract, never one of them
    rows = db.scalars(select(M.DocumentEvidence.id).where(
        M.DocumentEvidence.document_version_id == theirs.id)
        .order_by(M.DocumentEvidence.start_offset)).all()
    for e in rows[:2]:
        db.add(M.FindingEvidence(finding_id=finding.id, evidence_id=e,
                                 relationship_type=E.EvidenceRelationshipType.PRIMARY))
    db.flush()
    assert placed("UNRESOLVED") == (WHOLE_CONTRACT, {"whole": True,
                                                     "candidates": ["1", "2"]})
    assert placed("AMBIGUOUS")[0] == WHOLE_CONTRACT
    sign_in(api, db, lawyer)
    legal = _get(api, f"/contracts/{c.id}/brief")["legal"]
    assert [p["finding_id"] for p in legal["whole_contract"]] == [str(finding.id)]
    export = api.post(f"{V1}/reviews/{review.id}/export", json={"format": "docx"})
    assert export.status_code == 200
    plain = " ".join(_xml_text(export.content).split())
    assert "Whole contract" in plain and "Possibly in" not in plain
    assert "§" not in plain.split("Whole contract")[0][-80:]
    # round 5: the candidates reach a `legal.review` caller only — never the deal owner
    assert _get(api, f"/reviews/{review.id}/angles")["legal"]["items"][0]["case"][
        "contract"]["candidates"] == ["1", "2"]
    sign_in(api, db, owner)
    assert _get(api, f"/reviews/{review.id}/angles")["legal"]["items"][0]["case"][
        "contract"] == {"whole": True}
    sign_in(api, db, lawyer)
    # CONFIRMED: the clause is its place
    where, contract = placed("CONFIRMED")
    assert where == "Clause 1" and contract["clause"] == "1"


# ------------------------------------------------------------------ rule 18 (round 2)
def test_the_brief_decides_who_acts_next_on_the_server(api, db, owner, tmp_path):
    """The status is the server's code, from the one count and the stage; the screen
    only words it."""
    from legalmind.api.routers import deal_brief as B
    base = {"changes_total": 5, "changes_left": 5, "changes_left_legal": 4,
            "changes_left_for_me": 0, "points_open": 1, "sent_to_legal": True}
    owner_says = lambda stage=None, **over: B.status({**base, **over}, stage, legal=False)  # noqa: E731
    assert owner_says(sent_to_legal=False) == B.NOT_SENT
    assert owner_says() == B.WITH_LEGAL
    assert owner_says(changes_left_for_me=1) == B.WITH_LEGAL_AND_YOURS
    assert owner_says(changes_left_legal=0, changes_left_for_me=1) == B.YOURS_TO_ANSWER
    assert owner_says(changes_left_legal=0, changes_left=0) == B.POINTS_OPEN
    # round 3 (D1): an open point never sent to Legal is said, never "send our reply"
    assert owner_says(changes_left_legal=0, changes_left=0,
                      sent_to_legal=False) == B.SEND_POINTS_TO_LEGAL
    done = {"changes_left_legal": 0, "changes_left": 0, "points_open": 0, "changes_ours": 2}
    assert owner_says(**done) == B.SEND_REPLY
    assert B.status({**base, **done}, None, legal=False, had_legal=False) == B.ALL_ANSWERED
    assert owner_says("READY_TO_SEND", **done) == B.REPLY_READY
    assert owner_says("WITH_CLIENT", **done) == B.WITH_CLIENT
    assert B.status({"points_open": 2}, None, legal=False) is None       # no round
    assert B.status(base, None, legal=True) == B.LEGAL_QUEUE
    assert B.status({"points_open": 2}, None, legal=True) == B.LEGAL_POINTS
    assert B.status({"points_open": 0}, None, legal=True) == B.LEGAL_NOTHING
    # round 5: no analysed Review (points unknown) — never a send or "answered" code
    unknown = {k: v for k, v in {**base, **done}.items() if k != "points_open"}
    for stage in (None, "READY_TO_SEND"):
        assert owner_says(stage, **done) != B.CHECKING
        assert B.status(unknown, stage, legal=False) == B.CHECKING
    assert B.status({"changes_total": 2, "changes_left_legal": 0}, None,
                    legal=True) == B.CHECKING
    # over the API, for each reader
    c, theirs, review, lawyer = _deal(api, db, owner, tmp_path)
    # four changes with Legal, and the typography change is the owner's own
    assert _get(api, f"/contracts/{c.id}/brief")["status"] == B.WITH_LEGAL_AND_YOURS
    sign_in(api, db, lawyer)
    assert _get(api, f"/contracts/{c.id}/brief")["status"] == B.LEGAL_QUEUE


def test_a_stage_with_no_reply_to_send_never_says_send_our_reply():
    """UI-01 (2026-11-23): a Final contract told Sales "Send our reply". The deal's end
    wins over every count; Ready to sign and On hold say their own next act; every other
    stage keeps the count's code."""
    from legalmind.api.routers import deal_brief as B
    done = {"changes_total": 5, "changes_left": 0, "changes_left_legal": 0,
            "changes_left_for_me": 0, "points_open": 0, "sent_to_legal": True,
            "changes_ours": 2}
    busy = {**done, "changes_left": 2, "changes_left_for_me": 2}
    says = lambda counts, stage: B.status(counts, stage, legal=False)  # noqa: E731
    for counts in (done, busy, {"points_open": 0}, {}):    # whatever the counts say
        assert says(counts, "FINAL") == B.FINAL_READY
        assert says(counts, "SIGNED") is None              # the stage says it
    assert says(done, "READY_TO_SIGN") == B.PREPARE_FINAL
    assert says(done, "ON_HOLD") == B.ON_HOLD
    assert says(busy, "ON_HOLD") == B.YOURS_TO_ANSWER     # real work still comes first
    for stage in (None, "DRAFTING", "CLIENT_RETURNED", "INTERNAL_REVIEW"):
        assert says(done, stage) == B.SEND_REPLY
    # D1 (round 2): every change accepted and nothing waits on the client — the final
    # contract is next, as the To-do says (`todo.py` prepare_final); a wait keeps the reply
    accepted = {**done, "changes_ours": 0}
    assert says(accepted, "CLIENT_RETURNED") == B.PREPARE_FINAL
    assert says({**accepted, "points_waiting": 1}, "CLIENT_RETURNED") == B.SEND_REPLY
    for stage in (None, "DRAFTING", "INTERNAL_REVIEW"):   # the final may wait on Legal
        assert says(accepted, stage) != B.PREPARE_FINAL
    # Legal's codes read the queue, never the stage
    assert B.status(done, "FINAL", legal=True) == B.LEGAL_NOTHING


# ------------------------------------------------------------------ round 3
def test_a_decision_that_accepts_the_last_legal_row_tells_the_owner(api, db, owner, tmp_path):
    """Lead D2 (the verifier's A6a): no point open before the decision, and the decision
    (accepting the point) takes the last row off Legal's list — the owner is told once."""
    c, theirs, review, lawyer = _deal(api, db, owner, tmp_path)
    sign_in(api, db, lawyer)
    rows = _holder_rows(_changes(api, c))
    measured = next(r for r in rows if any(f["evaluation_ids"] for f in r["review"]["after"]))
    ev_id = measured["review"]["after"][0]["evaluation_ids"][0]
    for r in rows:
        if r["row_key"] != measured["row_key"]:
            assert api.post(_url(c, r["row_key"]), json={
                "answer": "keep_ours", "expected_version": 0}).status_code == 201
    for kind, seen in (("REQUIRE_COMPANY_STANDARD", 0), ("ACCEPT_DEVIATION", 1)):
        d = api.post(f"{V1}/evaluations/{ev_id}/decisions", json={
            "decision_type": kind, "justification": "Test decision",
            "expected_version": seen})
        assert d.status_code == 201, d.text
    counts = _get(api, f"/contracts/{c.id}")["counts"]
    assert counts["changes_left_legal"] == 0 and counts["points_open"] == 0
    assert _told_owner(db, c) == 1


def test_positions_wait_for_the_deal_to_be_with_legal(api, db, owner, tmp_path):
    """Lead D4 (the verifier's A2b): a department Lead holding legal.decision may not record
    on a deal never sent to Legal (403, in scope); a lawyer it was sent to may (201)."""
    from tests.test_negotiation import _contract
    dept = M.Department(name=f"D{uuid.uuid4().hex[:6]}", code=f"D{uuid.uuid4().hex[:6]}")
    db.add(dept)
    db.flush()
    owner.department_id = dept.id
    lead = make_user(db)
    lead.department_id = dept.id
    grant_role(db, lead, P.ROLE_DEPARTMENT_LEAD)
    grant_role(db, lead, P.ROLE_LEGAL_DECISION_AUTHORITY)
    db.flush()
    c = _contract(db, owner)
    _ingest(db, tmp_path, c, _docx(*OURS), "ours.docx")
    _ingest(db, tmp_path, c, _docx(*THEIRS), "theirs.docx")
    sign_in(api, db, lead)
    refused = _record(api, c)
    assert refused.status_code == 403, refused.text
    assert _get(api, f"/contracts/{c.id}/brief")["legal"]["can_record"] is False
    assert db.scalar(select(func.count()).select_from(M.DealPosition)) == 0


# ----------------------------------------------- batch 8 R2.5 (AM-461): not marked, first
def test_brief_lists_not_marked_changes_first_for_both_personas(api, db, owner, tmp_path):
    """Clause 2 changed silently, clause 3 deleted, clause 5 added — none marked; the
    tracked clause 1 and the typography-only clause 4 are not in it. The block comes
    before the asks and carries no position, so sales and Legal get the same one."""
    c, theirs, review, lawyer = _deal(api, db, owner, tmp_path)
    sales = _get(api, f"/contracts/{c.id}/brief")
    sign_in(api, db, lawyer)
    legal = _get(api, f"/contracts/{c.id}/brief")
    assert sales["not_marked"] == legal["not_marked"]
    block = sales["not_marked"]
    assert (block["count"], block["total"], block["more"]) == (3, 5, 0)
    assert block["highlights_read"] is True
    assert [r["clause"] for r in block["rows"]] == ["2", "3", "5"]
    keys = list(sales)
    assert keys.index("not_marked") < keys.index("asks")
    listed = _changes(api, c)
    assert listed["summary"]["unmarked"] == 3


def test_brief_omits_not_marked_when_every_change_is_marked(api, db, owner, tmp_path):
    c = _contract(db, owner)
    _ingest(db, tmp_path, c, _docx(*OURS), "ours.docx")
    _ingest(db, tmp_path, c, _docx(THEIRS[0], *OURS[1:]), "theirs.docx")
    brief = _get(api, f"/contracts/{c.id}/brief")
    assert "not_marked" not in brief and brief["asks"]
