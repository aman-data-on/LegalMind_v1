"""A client's changes, answered change by change — CLM Phase 1 (AB-150, 2026-11-02).

R1 every change once (a move is one row), R2 what the returned copy did not mark, R3 the
Review's own words per clause, R4 who may answer (fail closed: anything not positively
non-legal goes to a holder, `AM-250`), R5 answers keep their history (`AM-253`), and
`AM-260`'s "sent" recorded once. Every document here is synthetic; none names a client.
"""

from __future__ import annotations

import io
import json
import uuid
from urllib.parse import quote

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from legalmind.analysis import negotiation
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.ingestion.service import ingest_document
from legalmind.ingestion.storage import LocalFilesystemStorage
from legalmind.security import audit
from legalmind.security import permissions as P
from tests.conftest import (
    bespoke_role,
    grant,
    grant_role,
    make_evaluation,
    make_finding,
    make_user,
    sign_in,
)
from tests.test_version_comparison import V1, _version

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def _contract(db, owner, contract_type="MSA"):
    c = M.Contract(owner_id=owner.id, name="Negotiated MSA", contract_type=contract_type,
                   status=E.ContractStatus.ACTIVE)
    db.add(c)
    db.flush()
    return c


@pytest.fixture
def owner(api, db, seeded):
    user = make_user(db)
    user.name = "Owner"
    grant_role(db, user, P.ROLE_USER)
    sign_in(api, db, user)
    return user


def _url(contract, row_key=None):
    base = f"{V1}/contracts/{contract.id}/changes"
    return base if row_key is None else f"{base}/{quote(row_key, safe='')}/answers"


def _first(answer, **body):
    """An answer to a change nobody has answered yet (`expected_version` 0)."""
    return {"answer": answer, "expected_version": 0, **body}


def _changes(api, contract, **params):
    r = api.get(_url(contract), params=params)
    assert r.status_code == 200, r.text
    return r.json()["data"]


# ------------------------------------------------------------- R1 / R2 on real DOCX
def _docx(*paragraphs: str | list[str]) -> bytes:
    """Each paragraph plain text, or a list of raw run XML (tracked changes)."""
    import docx
    from docx.oxml import parse_xml
    d = docx.Document()
    for para in paragraphs:
        if isinstance(para, str):
            d.add_paragraph(para)
            continue
        p = d.add_paragraph()
        for xml in para:
            p._p.append(parse_xml(xml))
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def _run(t: str) -> str:
    return f'<w:r {W}><w:t xml:space="preserve">{t}</w:t></w:r>'


def _mark(tag: str, t: str, n: int) -> str:
    run = "delText" if tag in ("del", "moveFrom") else "t"
    return (f'<w:{tag} {W} w:id="{n}" w:author="Client" w:date="2026-11-01T00:00:00Z">'
            f'<w:r><w:{run} xml:space="preserve">{t}</w:{run}></w:r></w:{tag}>')


OURS = ["1. Fees are payable within 30 days of invoice.",
        "2. This Agreement is governed by the laws of India.",
        "3. Notices shall be given in writing to the registered office.",
        "4. The Term is one year from the Effective Date."]


def _ingest(db, tmp_path, contract, data, name):
    return ingest_document(db, LocalFilesystemStorage(tmp_path / "objects"),
                           contract_id=contract.id, uploaded_by=contract.owner_id,
                           data=data, filename=name, declared_mime=DOCX).document_version


def test_a_tracked_edit_is_tracked_and_only_the_silent_edit_is_flagged(db, owner, tmp_path):
    """R2 on a DOCX with real w:del/w:ins: clause 1 marked, clause 2 changed silently."""
    c = _contract(db, owner)
    ours = _ingest(db, tmp_path, c, _docx(*OURS), "ours.docx")
    theirs = _ingest(db, tmp_path, c, _docx(
        [_run("1. Fees are payable within "), _mark("del", "30", 1), _mark("ins", "60", 2),
         _run(" days of invoice.")],
        "2. This Agreement is governed by the laws of Singapore.", *OURS[2:]), "theirs.docx")
    listed = negotiation.changes(db, c, ours, theirs, legal_position=True)
    by = {ch["clause"]["number"]: ch for ch in listed["changes"]}
    assert set(by) == {"1", "2"} and listed["summary"]["modified"] == 2
    assert (by["1"]["tracked"], by["1"]["untracked"]) == (True, False)
    assert (by["2"]["tracked"], by["2"]["untracked"]) == (False, True)
    assert listed["summary"]["untracked"] == 1


def test_a_clean_returned_copy_flags_every_change_and_a_move_is_one_row(db, owner, tmp_path):
    """R1/R2: clauses 3 and 4 swapped in a clean copy — ONE moved row, untracked."""
    c = _contract(db, owner)
    ours = _ingest(db, tmp_path, c, _docx(*OURS), "ours.docx")
    theirs = _ingest(db, tmp_path, c, _docx(*OURS[:2], OURS[3], OURS[2]), "theirs.docx")
    listed = negotiation.changes(db, c, ours, theirs, legal_position=True)
    assert [ch["kind"] for ch in listed["changes"]] == ["MOVED"]
    moved = listed["changes"][0]
    assert moved["untracked"] and not moved["tracked"] and moved["route"] == "holder"


def test_a_tracked_move_from_and_to_is_one_moved_row(db, owner, tmp_path):
    """w:moveFrom / w:moveTo: Word's own move is one MOVED row, tracked, never a
    deletion plus an insertion."""
    c = _contract(db, owner)
    ours = _ingest(db, tmp_path, c, _docx(*OURS), "ours.docx")
    theirs = _ingest(db, tmp_path, c, _docx(
        *OURS[:2], [_mark("moveFrom", OURS[2], 1)], OURS[3], [_mark("moveTo", OURS[2], 2)]),
        "theirs.docx")
    listed = negotiation.changes(db, c, ours, theirs, legal_position=True)
    assert [(ch["kind"], ch["tracked"], ch["untracked"]) for ch in listed["changes"]] \
        == [("MOVED", True, False)]


def test_the_same_text_twice_lists_no_change(db, owner):
    c = _contract(db, owner)
    rows = [("1", "Fees", "1. Fees are payable within 30 days.")]
    listed = negotiation.changes(db, c, _version(db, c, 1, rows), _version(db, c, 2, rows),
                                 legal_position=True)
    assert listed["changes"] == [] and listed["summary"]["total"] == 0


def test_a_renumbered_clause_is_no_change_and_a_schedule_is_a_new_annexure(db, owner):
    c = _contract(db, owner)
    v1 = _version(db, c, 1, [("1", "Fees", "1. Fees are due monthly."),
                             ("2", "Law", "2. Governed by Indian law.")])
    v2 = _version(db, c, 2, [("1", "Scope", "1. The Services are hosting."),
                             ("2", "Fees", "2. Fees are due monthly."),
                             ("3", "Law", "3. Governed by Indian law."),
                             (None, None, "SCHEDULE A\nPrice list")])
    kinds = [(ch["kind"], ch["clause"]["number"])
             for ch in negotiation.changes(db, c, v1, v2, legal_position=True)["changes"]]
    assert kinds == [("ADDED", "1"), ("NEW_ANNEXURE", None)]


# ------------------------------------------------------------- R3 / R4 routing
def _review(db, version, findings):
    """A recorded Review on ``version``: (evidence index, classification, outcome)."""
    snap = M.ConfigurationSnapshot(snapshot_hash=uuid.uuid4().hex,
                                   created_by=version.uploaded_by)
    db.add(snap)
    db.flush()
    review = M.Review(contract_id=version.contract_id, document_version_id=version.id,
                      configuration_snapshot_id=snap.id,
                      status=E.ReviewStatus.ANALYSIS_COMPLETE, created_by=version.uploaded_by)
    db.add(review)
    db.flush()
    evidence = db.scalars(select(M.DocumentEvidence.id)
                          .where(M.DocumentEvidence.document_version_id == version.id)
                          .order_by(M.DocumentEvidence.start_offset)).all()
    for index, cls, outcome in findings:
        req = M.Requirement(code=f"LIAB-{uuid.uuid4().hex[:6]}", status=E.ConfigStatus.ACTIVE)
        db.add(req)
        db.flush()
        rv = M.RequirementVersion(requirement_id=req.id, version_number=1, name="Liability",
                                  evaluator_type=E.EvaluatorType.NUMERIC_COMPARISON,
                                  created_by=version.uploaded_by)
        db.add(rv)
        db.flush()
        finding = make_finding(db, review, rv, classification=cls)
        ev = make_evaluation(db, finding, classification=cls, rule_outcome=outcome)
        db.add(M.EvaluationEvidence(evaluation_id=ev.id, evidence_id=evidence[index],
                                    relationship_type=E.EvidenceRelationshipType.PRIMARY))
    db.flush()
    return review


LIAB = ("9", "Limitation of Liability")


def _pair(db, contract, before_text, after_text):
    return (_version(db, contract, 1, [(*LIAB, before_text)]),
            _version(db, contract, 2, [(*LIAB, after_text)]))


def test_the_review_words_are_quoted_and_the_delta_shown(db, owner):
    """R3: the status word is the recorded Review's (`by_finding`), per version."""
    c = _contract(db, owner)
    v1, v2 = _pair(db, c, "9. Liability is capped at 12 months of fees.",
                   "9. Liability is capped at 3 months of fees.")
    _review(db, v1, [(0, E.FindingClassification.MATCH, E.RuleOutcome.ACCEPTABLE)])
    _review(db, v2, [(0, E.FindingClassification.DEVIATION, E.RuleOutcome.UNACCEPTABLE)])
    change = negotiation.changes(db, c, v1, v2, legal_position=True)["changes"][0]
    assert [f["user_status"] for f in change["review"]["before"]] == ["ACCEPTABLE"]
    assert [f["user_status"] for f in change["review"]["after"]] == ["REQUIRES_MODIFICATION"]
    assert change["review"]["after"][0]["evaluation_ids"]       # decided through these
    assert {d["before"] or d["after"] for d in change["review_delta"]} \
        == {"ACCEPTABLE", "REQUIRES_MODIFICATION"}
    assert change["route"] == "holder" and change["route_reason"] == negotiation.MEASURED


@pytest.mark.parametrize(("before", "after", "findings", "route"), [
    # an unmeasured substantive edit, and an added clause nothing maps: a holder
    ("9. Liability is capped.", "9. Liability is uncapped.", [], "holder"),
    # a MATCH after a punctuation-only change is no change for us: the owner (AM-299)
    ("9. Liability is capped, always.", "9. Liability is capped; always",
     [(0, E.FindingClassification.MATCH, E.RuleOutcome.ACCEPTABLE)], "owner"),
    # a MATCH after changed WORDS is a holder's (AM-317 r1, audit N1)
    ("9. Liability is capped.", "9. Liability is capped at fees.",
     [(0, E.FindingClassification.MATCH, E.RuleOutcome.ACCEPTABLE)], "holder"),
    # the approved favourable rule accepted the deviation (AM-239)
    ("9. Liability is capped.", "9. Liability is capped lower.",
     [(0, E.FindingClassification.DEVIATION, E.RuleOutcome.ACCEPTABLE)], "favour"),
    # typography only, nothing measured: the owner answers
    ("9. The Customer\u2019s fees \u2014 monthly.", "9. The Customer's fees - monthly.",
     [], "owner"),
])
def test_routing_fails_closed_to_a_holder(db, owner, before, after, findings, route):
    c = _contract(db, owner)
    v1, v2 = _pair(db, c, before, after)
    _review(db, v2, findings)
    assert negotiation.changes(db, c, v1, v2, legal_position=True)["changes"][0]["route"] \
        == route


def test_favour_needs_every_changed_row_measured_in_our_favour(db, owner):
    """A unit whose numbered row moved in our favour and whose sub-paragraph changed
    unmeasured is a holder's, never the owner's on the strength of the first row."""
    c = _contract(db, owner)
    v1 = _version(db, c, 1, [(*LIAB, "9. Liability is capped."),
                             (None, None, "Notices go by post.")])
    v2 = _version(db, c, 2, [(*LIAB, "9. Liability is capped lower."),
                             (None, None, "Notices go by email.")])
    _review(db, v2, [(0, E.FindingClassification.DEVIATION, E.RuleOutcome.ACCEPTABLE),
                     (1, E.FindingClassification.DEVIATION, E.RuleOutcome.ACCEPTABLE)])
    v3 = _version(db, c, 3, [(*LIAB, "9. Liability is capped lower."),
                             (None, None, "Notices go by email.")])
    _review(db, v3, [(0, E.FindingClassification.DEVIATION, E.RuleOutcome.ACCEPTABLE)])
    both = negotiation.changes(db, c, v1, v2, legal_position=True)["changes"]
    [first_only] = negotiation.changes(db, c, v1, v3, legal_position=True)["changes"]
    assert [ch["route"] for ch in both] == ["favour"]
    assert first_only["route"] == "holder"


def test_the_default_pair_is_theirs_against_our_latest(api, db, owner):
    """Two client copies in a row: the changes (and so the reply) are against OUR
    version, never the client's own earlier copy."""
    c = _contract(db, owner)
    for n, (role, cap) in enumerate((("COMPANY_DRAFT", "12"), ("CLIENT_MODIFIED", "9"),
                                     ("CLIENT_MODIFIED", "6")), start=1):
        v = _version(db, c, n, [(*LIAB, f"9. Liability is capped at {cap} months.")])
        v.doc_metadata = {"version_role": role}
    db.flush()
    listed = _changes(api, c)
    assert (listed["from"]["version_number"], listed["to"]["version_number"]) == (1, 3)


def test_the_owner_cannot_accept_a_change_a_holder_decides(api, db, owner):
    c = _contract(db, owner)
    _pair(db, c, "9. Liability is capped.", "9. Liability is uncapped.")
    change = _changes(api, c)["changes"][0]
    assert change["route"] == "holder"
    r = api.post(_url(c, change["row_key"]), json=_first("accept_theirs"))
    assert r.status_code == 403 and r.json()["error"]["code"] == "LEGAL_DECISION_REQUIRED"
    assert db.scalar(select(func.count()).select_from(M.ComparisonChoice)) == 0
    # keeping our position needs no one else
    assert api.post(_url(c, change["row_key"]), json=_first("keep_ours")).status_code \
        == 201


def test_the_owner_may_accept_a_change_in_our_favour(api, db, owner):
    c = _contract(db, owner)
    _, v2 = _pair(db, c, "9. Liability is capped.", "9. Liability is capped lower.")
    _review(db, v2, [(0, E.FindingClassification.DEVIATION, E.RuleOutcome.ACCEPTABLE)])
    change = _changes(api, c)["changes"][0]
    assert change["route"] == "favour" and change["favour_reason"]
    r = api.post(_url(c, change["row_key"]),
                 json=_first("accept_theirs", reason="lower cap is ours"))
    assert r.status_code == 201, r.text
    assert r.json()["data"]["answer"]["answer"] == "accept_theirs"


def test_position_text_is_omitted_for_a_position_blind_reader(api, db, seeded):
    """LEGAL-02 / SEC-07: the Constitution's position is ABSENT, never blanked."""
    reader = make_user(db)
    grant(db, reader, bespoke_role(db, "BLIND_READER", [P.CONTRACT_VIEW, P.DOCUMENT_VIEW]))
    c = _contract(db, reader)
    _pair(db, c, "9. Liability is capped at the fees paid.",
          "9. Liability is capped at the fees paid in the last month.")
    sign_in(api, db, reader)
    blind = api.get(_url(c))
    topics = blind.json()["data"]["changes"][0]["triage"]["topics"]
    assert topics and all("position" not in t for t in topics)
    seeing = negotiation.changes(db, c, *db.scalars(
        select(M.DocumentVersion).where(M.DocumentVersion.contract_id == c.id)
        .order_by(M.DocumentVersion.version_number)).all(), legal_position=True)
    position = seeing["changes"][0]["triage"]["topics"][0]["position"]
    assert position and position not in blind.text
    assert blind.json()["data"]["can_answer"] is False


def test_out_of_scope_is_the_byte_identical_404(api, db, owner):
    theirs = _contract(db, make_user(db))
    _pair(db, theirs, "9. A.", "9. B.")

    def body(r):
        assert r.status_code == 404
        payload = r.json()
        payload["error"]["request_id"] = "-"
        return json.dumps(payload, sort_keys=True)

    ghost = M.Contract(id=uuid.uuid4(), owner_id=owner.id, name="x")
    key = quote("MODIFIED|a|b", safe="")
    bodies = {body(api.get(_url(theirs))), body(api.get(_url(ghost))),
              body(api.post(f"{_url(theirs)}/{key}/answers", json=_first("keep_ours")))}
    assert len(bodies) == 1


def test_a_lead_or_a_collaborator_answers_and_a_moved_collaborator_may_not(api, db, seeded):
    """AM-259 r2: the owner, a collaborator or the department Lead writes. AM-280: a
    collaborator READS that contract too — while still in the owner's department; a
    department move ends the read and the write at once (r2)."""
    sales, other = (M.Department(code=f"S{uuid.uuid4().hex[:5]}", name=n)
                    for n in ("Sales", "Other"))
    db.add_all([sales, other])
    db.flush()
    boss, lead, mate = make_user(db), make_user(db), make_user(db)
    for u, role in ((boss, P.ROLE_USER), (lead, P.ROLE_DEPARTMENT_LEAD),
                    (mate, P.ROLE_USER)):
        u.department_id = sales.id
        grant_role(db, u, role)
    c = _contract(db, boss)
    _pair(db, c, "9. Liability is capped.", "9. Liability is uncapped.")
    sign_in(api, db, lead)
    listed = _changes(api, c)
    key = listed["changes"][0]["row_key"]
    assert listed["can_answer"] is True
    assert api.post(_url(c, key), json=_first("keep_ours")).status_code == 201

    sign_in(api, db, mate)                      # same department, no scope: nothing
    assert api.get(_url(c)).status_code == 404
    assert api.get(f"{V1}/contracts/{c.id}").status_code == 404
    db.add(M.ContractCollaborator(contract_id=c.id, user_id=mate.id, added_by=boss.id))
    db.flush()
    assert api.get(f"{V1}/contracts/{c.id}").status_code == 200
    assert _changes(api, c)["can_answer"] is True
    r = api.post(_url(c, key), json={"answer": "keep_ours", "reason": "ours",
                                     "expected_version": 1})
    assert r.status_code == 201, r.text
    assert db.scalars(select(M.Notification.kind).where(
        M.Notification.user_id == lead.id)).all() == ["ANSWER_CHANGED_BY_COLLEAGUE"]

    mate.department_id = other.id               # moved: the row stays, the right ends
    db.flush()
    assert api.get(f"{V1}/contracts/{c.id}").status_code == 404
    assert api.get(_url(c)).status_code == 404
    assert api.post(_url(c, key), json={"answer": "keep_ours", "expected_version": 2}) \
        .status_code == 404


# ------------------------------------------------------------- R5 history
def test_answers_keep_their_history_across_three_rounds(api, db, owner):
    """R5: each answer a new row; a change's line runs through every earlier round of
    the same clause (`AM-253` r2'), oldest first."""
    c = _contract(db, owner)
    _version(db, c, 1, [(*LIAB, "9. Liability is capped at 12 months of fees.")])
    for to, cap, reason in ((2, "9", "first round"), (3, "6", "second round"),
                            (4, "3", "third round")):
        _version(db, c, to, [(*LIAB, f"9. Liability is capped at {cap} months of fees.")])
        key = _changes(api, c, to_version=to)["changes"][0]["row_key"]
        r = api.post(_url(c, key), params={"to_version": to},
                     json={"answer": "keep_ours", "reason": reason, "expected_version": 0})
        assert r.status_code == 201, r.text
    line = _changes(api, c)["changes"][0]
    assert [(h["round"], h["answer"], h["reason"], h["decided_by"])
            for h in line["history"]] == [
        (2, "keep_ours", "first round", "Owner"), (3, "keep_ours", "second round", "Owner"),
        (4, "keep_ours", "third round", "Owner")]
    assert line["answer"]["round"] == 4
    assert db.scalar(select(func.count()).select_from(M.ComparisonChoice)) == 3


def test_an_answer_to_a_superseded_client_version_is_refused(api, db, owner):
    """L6: once the client sent a newer version, the older round takes no answer."""
    c = _contract(db, owner)
    for n, cap in enumerate(("12", "9", "6"), start=1):
        v = _version(db, c, n, [(*LIAB, f"9. Liability is capped at {cap} months of fees.")])
        if n > 1:
            v.doc_metadata = {"version_role": "CLIENT_MODIFIED"}
    db.flush()
    key = _changes(api, c, to_version=2, from_version=1)["changes"][0]["row_key"]
    r = api.post(_url(c, key), params={"to_version": 2, "from_version": 1},
                 json=_first("keep_ours"))
    assert r.status_code == 409 and "latest version" in r.json()["error"]["message"]


def test_a_stale_answer_is_409_never_a_silent_overwrite(api, db, owner):
    c = _contract(db, owner)
    _pair(db, c, "9. Liability is capped.", "9. Liability is uncapped.")
    key = _changes(api, c)["changes"][0]["row_key"]
    first = api.post(_url(c, key), json=_first("keep_ours"))
    assert first.status_code == 201
    stale = api.post(_url(c, key), json={"answer": "keep_ours", "reason": "again",
                                         "expected_version": 0})
    assert stale.status_code == 409 and "colleague" in stale.json()["error"]["message"]
    again = api.post(_url(c, key), json={"answer": "keep_ours", "reason": "again",
                                         "expected_version": 1})
    assert again.status_code == 201
    assert [h["version_number"] for h in again.json()["data"]["history"]] == [1, 2]


def test_choices_are_append_only_and_still_go_with_their_contract(api, db, owner):
    c = _contract(db, owner)
    _pair(db, c, "9. Liability is capped.", "9. Liability is uncapped.")
    key = _changes(api, c)["changes"][0]["row_key"]
    api.post(_url(c, key), json=_first("keep_ours"))
    for sql in ("UPDATE comparison_choices SET choice = 'theirs'",
                "DELETE FROM comparison_choices"):
        with pytest.raises(DBAPIError, match="append-only"), db.begin_nested():
            db.execute(text(sql))
    db.execute(text("DELETE FROM contracts WHERE id = :id"), {"id": c.id})
    assert db.scalar(select(func.count()).select_from(M.ComparisonChoice)) == 0


# ------------------------------------------------------------- AM-260 sent
def test_a_version_is_marked_sent_once_and_audited(api, db, owner):
    c = _contract(db, owner)
    version = _version(db, c, 1, [(*LIAB, "9. Liability is capped.")])
    url = f"{V1}/document-versions/{version.id}/mark-sent"
    r = api.post(url)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["sent_by"] == str(owner.id) and r.json()["data"]["sent_at"]
    assert api.post(url).status_code == 409
    assert db.scalar(select(func.count()).select_from(M.AuditEvent).where(
        M.AuditEvent.action == audit.DOCUMENT_VERSION_SENT,
        M.AuditEvent.entity_id == version.id)) == 1
    sign_in(api, db, make_user(db))
    assert api.post(url).status_code == 404


def test_a_collaborator_marks_ours_sent_and_never_the_clients(api, db, owner):
    """AM-259 r2: the negotiation resolver records "sent"; only one of OUR versions."""
    team = M.Department(code=f"T{uuid.uuid4().hex[:6]}", name="Team")
    db.add(team)
    db.flush()
    mate = make_user(db)
    grant_role(db, mate, P.ROLE_USER)
    owner.department_id = mate.department_id = team.id
    c = _contract(db, owner)
    db.add(M.ContractCollaborator(contract_id=c.id, user_id=mate.id, added_by=owner.id))
    ours, theirs = _pair(db, c, "9. Liability is capped.", "9. Liability is uncapped.")
    theirs.doc_metadata = {"version_role": "CLIENT_MODIFIED"}
    db.flush()
    sign_in(api, db, mate)
    assert api.post(f"{V1}/document-versions/{theirs.id}/mark-sent").status_code == 422
    r = api.post(f"{V1}/document-versions/{ours.id}/mark-sent")
    assert r.status_code == 200 and r.json()["data"]["sent_by"] == str(mate.id)


def test_keep_ours_on_every_formatting_change_is_one_write_all_or_none(api, db, owner):
    """CLM page 3: the formatting-only rows (the owner's route) answered together. A
    legal row among them, or one a colleague answered first, refuses the whole request
    and writes nothing."""
    c = _contract(db, owner)
    rows = [("9", "Fees", "9. The Customer\u2019s fees \u2014 monthly."),
            ("10", "Notices", "10. Notices \u2014 by post."),
            ("11", "Liability", "11. Liability is capped.")]
    _version(db, c, 1, rows)
    _version(db, c, 2, [(*rows[0][:2], "9. The Customer's fees - monthly."),
                        (*rows[1][:2], "10. Notices - by post."),
                        (*rows[2][:2], "11. Liability is uncapped.")])
    listed = _changes(api, c)["changes"]
    fmt = [ch["row_key"] for ch in listed if ch["route_reason"] == negotiation.FORMATTING_ONLY]
    legal = [ch["row_key"] for ch in listed if ch["route"] == "holder"]
    assert len(fmt) == 2 and len(legal) == 1
    url = f"{_url(c)}/formatting/keep-ours"
    mixed = api.post(url, json={"row_keys": [*fmt, *legal]})
    assert mixed.status_code == 422, mixed.text
    assert db.scalar(select(func.count()).select_from(M.ComparisonChoice)) == 0
    api.post(_url(c, fmt[0]), json=_first("accept_theirs"))       # a colleague first
    assert api.post(url, json={"row_keys": fmt}).status_code == 409
    assert db.scalar(select(func.count()).select_from(M.ComparisonChoice)) == 1
    done = api.post(url, json={"row_keys": fmt[1:]})
    assert done.status_code == 201, done.text
    assert [r["answer"]["answer"] for r in done.json()["data"]["rows"]] == ["keep_ours"]
    assert {ch["row_key"]: (ch["answer"] or {}).get("answer") for ch in _changes(api, c)
            ["changes"]} == {fmt[0]: "accept_theirs", fmt[1]: "keep_ours", legal[0]: None}


# ------------------------------------------------------------- AM-317 r3 (audit N2)
def test_a_shifted_definition_pairs_by_its_term_never_by_its_number(db, owner):
    """The client deleted one definition and added another (synthetic wording): their
    1.2 "Business Day" is our 1.3, never our 1.2 "AUP"; the added and the deleted
    definition each stand on one side only."""
    c = _contract(db, owner)
    v1 = _version(db, c, 1, [
        ("1.1", None, "1.1 \u201cAffiliate\u201d shall mean an entity under common control."),
        ("1.2", None, "1.2 \u201cAUP\u201d shall mean the acceptable usage policy."),
        ("1.3", None, "1.3 \u201cBusiness Day\u201d shall mean a day banks at Pune are open.")])
    v2 = _version(db, c, 2, [
        ("1.1", None, "1.1 \u201cAffiliate\u201d shall mean an entity under common control."),
        ("1.2", None, "1.2 \u201cBusiness Day\u201d shall mean a day banks at Bangalore "
                      "are open."),
        ("1.3", None, "1.3 \u2018Business Data\u2019 means any data the Customer hosts.")])
    rows = negotiation.changes(db, c, v1, v2, legal_position=True)["changes"]
    by = {(ch["kind"], (ch["before"] or {}).get("text", "")[:16],
           (ch["after"] or {}).get("text", "")[:16]) for ch in rows}
    assert by == {("MODIFIED", "1.3 \u201cBusiness Da", "1.2 \u201cBusiness Da"),
                  ("DELETED", "1.2 \u201cAUP\u201d shall ", ""),
                  ("ADDED", "", "1.3 \u2018Business Da")}


def test_a_reworded_clause_still_pairs_by_its_number_when_nothing_says_otherwise(
        db, owner):
    """The number is the last resort, not dropped: a clause reworded past similarity,
    under the same heading, is still one MODIFIED clause."""
    c = _contract(db, owner)
    v1, v2 = _pair(db, c, "9. Liability is capped at twelve months of fees.",
                   "9. Neither side owes more than a year's charges.")
    [row] = negotiation.changes(db, c, v1, v2, legal_position=True)["changes"]
    assert row["kind"] == "MODIFIED"
