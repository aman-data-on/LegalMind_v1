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
    """Declared as every upload is (`AM-324` r4; P1: an undeclared version is no one's)
    by its test name — ours / o / reply ours, theirs / t the client's; any other name
    stays undeclared, as the test that names it sets it."""
    version = ingest_document(db, LocalFilesystemStorage(tmp_path / "objects"),
                              contract_id=contract.id, uploaded_by=contract.owner_id,
                              data=data, filename=name, declared_mime=DOCX).document_version
    role = _ROLE_BY_NAME.get(name.removesuffix(".docx"))
    if role:
        version.doc_metadata = {**(version.doc_metadata or {}), "version_role": role}
        db.flush()
    return version


_ROLE_BY_NAME = {"ours": "COMPANY_DRAFT", "o": "COMPANY_DRAFT", "reply": "COMPANY_DRAFT",
                 "theirs": "CLIENT_MODIFIED", "t": "CLIENT_MODIFIED"}


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
def _review(db, version, findings, code=None):
    """A recorded Review on ``version``: (evidence index, classification, outcome);
    ``code``: one requirement code for every finding (the same standard on two
    versions), else a fresh one each."""
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
        req = db.scalar(select(M.Requirement).where(M.Requirement.code == code)) \
            if code else None
        if req is None:
            req = M.Requirement(code=code or f"LIAB-{uuid.uuid4().hex[:6]}",
                                status=E.ConfigStatus.ACTIVE)
            db.add(req)
            db.flush()
        rv = db.scalar(select(M.RequirementVersion).where(
            M.RequirementVersion.requirement_id == req.id))
        if rv is None:
            rv = M.RequirementVersion(requirement_id=req.id, version_number=1,
                                      name="Liability",
                                      evaluator_type=E.EvaluatorType.NUMERIC_COMPARISON,
                                      created_by=version.uploaded_by)
            db.add(rv)
            db.flush()
        finding = make_finding(db, review, rv, classification=cls)
        ev = make_evaluation(db, finding, classification=cls, rule_outcome=outcome)
        # as the evaluator stamps every Evaluation (D-2): the mapping was CONFIRMED
        ev.result = {**ev.result, "evaluated_facts": {"mapping_state": "CONFIRMED"}}
        db.add(M.EvaluationEvidence(evaluation_id=ev.id, evidence_id=evidence[index],
                                    relationship_type=E.EvidenceRelationshipType.PRIMARY))
    db.flush()
    return review


LIAB = ("9", "Limitation of Liability")


def _pair(db, contract, before_text, after_text):
    """Ours, then the client's — each declared (P1)."""
    ours = _version(db, contract, 1, [(*LIAB, before_text)])
    theirs = _version(db, contract, 2, [(*LIAB, after_text)])
    ours.doc_metadata = {"version_role": "COMPANY_DRAFT"}
    theirs.doc_metadata = {"version_role": "CLIENT_MODIFIED"}
    db.flush()
    return ours, theirs


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


def test_a_version_nobody_declared_is_never_ours(api, db, owner):
    """P1 (owner, 2026-11-09): v2 has no role and the same file as the client's v3. It is
    never taken as ours — the changes, the final contract and the counts stop and ask
    whose paper it is (rule 15); once declared the client's, the pair is v1 -> v3."""
    c = _contract(db, owner)
    v1, v2, v3 = (_version(db, c, n, [(*LIAB, f"9. Liability is capped at {cap} months.")])
                  for n, cap in ((1, "12"), (2, "3"), (3, "3")))
    v1.doc_metadata = {"version_role": "COMPANY_DRAFT"}
    v3.doc_metadata = {"version_role": "CLIENT_MODIFIED"}
    v2.file_hash = v3.file_hash
    db.flush()
    r = api.get(_url(c))
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "VERSION_ROLE_UNDECLARED"
    assert r.json()["error"]["version_number"] == 2
    assert "version 2" in r.json()["error"]["message"]
    plan = api.get(f"{V1}/contracts/{c.id}/package").json()["data"]
    assert "VERSION_ROLE_UNDECLARED" in {b["code"] for b in plan["blockers"]}
    assert api.post(f"{V1}/contracts/{c.id}/reply").status_code == 422
    assert api.get(f"{V1}/contracts/{c.id}").status_code == 200       # counts: none
    assert api.patch(f"{V1}/document-versions/{v2.id}",
                     json={"version_role": "CLIENT_MODIFIED"}).status_code == 200
    listed = _changes(api, c)
    assert (listed["from"]["version_number"], listed["to"]["version_number"]) == (1, 3)
    assert len(listed["changes"]) == 1


def test_a_reviewed_version_nobody_declared_is_declared_once_then_compared(api, db, owner):
    """P1 / `AM-340` (proposed): a legacy v2 with a Review and no role is declared the
    client's after review — audited as its own event, no "client returned" notice — and
    the Changes tab works. A role once declared on a reviewed version never changes."""
    c = _contract(db, owner)
    v1 = _version(db, c, 1, [(*LIAB, "9. Liability is capped at 12 months.")])
    v2 = _version(db, c, 2, [(*LIAB, "9. Liability is capped at 3 months.")])
    v1.doc_metadata = {"version_role": "COMPANY_DRAFT"}
    _review(db, v2, [(0, E.FindingClassification.DEVIATION, E.RuleOutcome.UNACCEPTABLE)])
    db.flush()
    assert api.get(_url(c)).json()["error"]["code"] == "VERSION_ROLE_UNDECLARED"
    url = f"{V1}/document-versions/{v2.id}"
    assert api.patch(url, json={"version_role": "FINAL_SIGNED"}).status_code == 409
    assert api.patch(url, json={"version_role": "CLIENT_MODIFIED",
                                "counterparty": "X"}).status_code == 409   # role only
    assert api.patch(url, json={"version_role": "CLIENT_MODIFIED"}).status_code == 200
    listed = _changes(api, c)
    assert (listed["from"]["version_number"], listed["to"]["version_number"]) == (1, 2)
    [event] = db.execute(select(M.AuditEvent).where(
        M.AuditEvent.action == audit.DOCUMENT_ROLE_DECLARED_AFTER_REVIEW)).scalars().all()
    assert (event.before_state["version_role"], event.after_state["version_role"]) == (
        None, "CLIENT_MODIFIED") and event.actor_id == owner.id
    assert db.scalar(select(func.count()).select_from(M.Notification)) == 0
    # declared now: changing it on a reviewed version stays refused (locked 33.7)
    assert api.patch(url, json={"version_role": "COMPANY_DRAFT"}).status_code == 409
    assert api.patch(url, json={"version_role": None}).status_code == 409


@pytest.mark.parametrize("used", ["sent", "answered"])
def test_a_reviewed_version_already_used_as_ours_is_declared_ours_only(api, db, owner, used):
    """`AM-340` r6: a legacy version LegalMind already treated as ours — recorded as sent,
    or the left side of an answer — is late-declared ours, never the client's."""
    c = _contract(db, owner)
    v1, v2 = _pair(db, c, "9. Liability is capped.", "9. Liability is uncapped.")
    if used == "answered":
        key = _changes(api, c)["changes"][0]["row_key"]
        assert api.post(_url(c, key), json=_first("keep_ours")).status_code == 201
    v1.doc_metadata = None
    if used == "sent":
        v1.sent_at, v1.sent_by = v1.created_at, owner.id
    _review(db, v1, [(0, E.FindingClassification.MATCH, E.RuleOutcome.ACCEPTABLE)])
    db.flush()
    url = f"{V1}/document-versions/{v1.id}"
    r = api.patch(url, json={"version_role": "CLIENT_MODIFIED"})
    assert r.status_code == 409 and "already used as ours" in r.json()["error"]["message"]
    assert api.patch(url, json={"version_role": "COMPANY_DRAFT"}).status_code == 200


def test_an_answer_naming_an_undeclared_side_is_refused(api, db, owner):
    """P1: a pair named by from_version / to_version is never compared on a version
    nobody declared — the answer is refused, nothing written."""
    c = _contract(db, owner)
    v1, v2 = _pair(db, c, "9. Liability is capped.", "9. Liability is uncapped.")
    key = _changes(api, c)["changes"][0]["row_key"]
    v1.doc_metadata = None
    db.flush()
    r = api.post(_url(c, key), params={"from_version": 1, "to_version": 2},
                 json=_first("keep_ours"))
    assert r.status_code == 422 and r.json()["error"]["code"] == "VERSION_ROLE_UNDECLARED"
    assert r.json()["error"]["version_number"] == 1
    assert db.scalar(select(func.count()).select_from(M.ComparisonChoice)) == 0


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
    _version(db, c, 1, [(*LIAB, "9. Liability is capped at 12 months of fees.")]
             ).doc_metadata = {"version_role": "COMPANY_DRAFT"}
    for to, cap, reason in ((2, "9", "first round"), (3, "6", "second round"),
                            (4, "3", "third round")):
        _version(db, c, to, [(*LIAB, f"9. Liability is capped at {cap} months of fees.")]
                 ).doc_metadata = {"version_role": "COMPANY_DRAFT"}     # as undeclared was
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
        v.doc_metadata = {"version_role": "CLIENT_MODIFIED" if n > 1 else "COMPANY_DRAFT"}
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
    version.doc_metadata = {"version_role": "COMPANY_DRAFT"}
    db.flush()
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
    _version(db, c, 1, rows).doc_metadata = {"version_role": "COMPANY_DRAFT"}
    _version(db, c, 2, [(*rows[0][:2], "9. The Customer's fees - monthly."),
                        (*rows[1][:2], "10. Notices - by post."),
                        (*rows[2][:2], "11. Liability is uncapped.")]
             ).doc_metadata = {"version_role": "CLIENT_MODIFIED"}
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


def test_a_recitals_joining_word_is_never_a_change_of_its_own():
    """Verifier item 7: "AND" / "WHEREAS" on their own heading line stay with the text
    above them — they are not units, so they are never counted as changes."""
    from legalmind.analysis.negotiation import _units
    from legalmind.mapping.engine import Clause
    rows = [Clause(uuid.uuid4(), "THIS AGREEMENT is made between A", is_heading=True),
            Clause(uuid.uuid4(), "AND", is_heading=True),
            Clause(uuid.uuid4(), "B, the second party", is_heading=False),
            Clause(uuid.uuid4(), "WHEREAS", is_heading=True),
            Clause(uuid.uuid4(), "Definitions", section_number="1", is_heading=True)]
    units = _units(rows)
    assert [u["number"] for u in units] == [None, "1"]
    assert "AND" in units[0]["text"] and "WHEREAS" in units[0]["text"]


def _rows_of(*pair: bytes) -> list[str]:
    """Each change between two DOCX files as "KIND number|heading", read as the change
    list reads them (parse → clauses → units → alignment), no database."""
    from legalmind.ingestion.parsing import parse_docx
    from legalmind.mapping.engine import Clause
    from legalmind.mapping.service import _marks
    old, new = (negotiation._units([
        Clause(uuid.uuid4(), s.content, s.section_number, s.section_title,
               is_heading=bool(s.metadata.get("heading")), marks=_marks(s.metadata))
        for s in parse_docx(data).segments]) for data in pair)
    out = []
    for i, j, moved in negotiation._align(old, new):
        o, n = (old[i] if i is not None else None), (new[j] if j is not None else None)
        if kind := negotiation._kind(o, n, moved):
            here = n or o
            assert here is not None
            out.append(f"{kind} {here['number'] or here['heading']}")
    return out


def _with_table(paragraphs: list[str], cell: str) -> bytes:
    import docx
    d = docx.Document()
    for para in paragraphs:
        d.add_paragraph(para)
    d.add_paragraph("Execution", style="Heading 1")
    row = d.add_table(rows=1, cols=2).rows[0]
    row.cells[0].text, row.cells[1].text = cell, "For the Customer Name: ___"
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def test_one_change_to_a_long_sub_clause_or_a_signature_block_is_one_row():
    """Batch 6 (2026-11-20): a long "1.2. ‘Widget’…" or "4.1.3. suspension…" lost
    its number, so the change read as clause 1.1 modified plus 1.2 added (or 4.1.3
    deleted plus 4.1.2 modified); a Heading-1 "Execution" over a signature table had
    its cell's change filed under 9.4. Each is now exactly one row."""
    tail = " and every replacement of it supplied under an order form" * 4
    ours = ["1.1. \"Alpha\" means the first thing.",
            "1.2. \u2018Widget\u2019 shall mean any part" + tail + ".",
            "1.3. \"Gamma\" means the third thing."]
    theirs = [ours[0], [_run("1.2. \u2018Widget\u2019 shall mean any "),
                        _mark("ins", "spare ", 1), _run("part" + tail + ".")], ours[2]]
    assert _rows_of(_docx(*ours), _docx(*theirs)) == ["MODIFIED 1.2"]

    lead = ["4.1. The provider may suspend if:", "4.1.1. a threat;", "4.1.2. a breach;"]
    longer = ("4.1.3. suspension required by law or by a binding direction of a competent "
              "authority" + ", and the provider shall restore the service promptly once "
              "the grounds cease" * 2 + ".")
    assert _rows_of(_docx(*lead, "4.1.3. suspension is required by law."),
                    _docx(*lead, longer)) == ["MODIFIED 4.1.3"]

    body = ["9.4. Counterparts: This agreement may be signed in counterparts."]
    assert _rows_of(_with_table(body, "For the Provider Name: ___"),
                    _with_table(body, "For the Provider Name: Provider Pvt Ltd")) \
        == ["MODIFIED Execution"]


# ------------------------------------------- R2 S2/S3/S9 (owner, 2026-11-16)
def test_each_change_carries_its_lettered_points_and_the_review_table(api, db, owner):
    """The lawyer's view rides on each change (display only) and the internal review
    table lists every change, undecided ones as "Not decided yet", decided ones with
    the clause as the answer leaves it; the Word file is audited."""
    c = _contract(db, owner)
    _pair(db, c, "9. Liability is capped at 12 months. The Customer shall pay on time.",
           "9. Liability is capped at 6 months. The Customer shall pay on time. "
           "LeapSwitch shall indemnify the Customer.")
    listed = _changes(api, c)
    assert listed["notes_for_legal"] == []
    change = listed["changes"][0]
    lettered = change["lawyer"]["points"]
    assert [(p["letter"], p["kind"]) for p in lettered] == [("a", "CHANGED"), ("b", "ADDED")]
    assert lettered[1]["bound"] == "LEAPSWITCH"
    assert change["lawyer"]["standards"]["source"] in ("HEADING_TOPIC", "LEGAL_DECIDES")

    table = api.get(f"{_url(c)}/review-table")
    assert table.status_code == 200, table.text
    got = table.json()["data"]
    assert got["head"] == ["Sr", "Clause", "Original", "Requested change",
                           "Effect for us", "Source", "Updated clause", "Recommendation"]
    assert got["rows"][0][6:] == ["Not decided yet", "Not decided yet"]
    assert got["rows"][0][3].startswith("(a) ")
    assert api.post(_url(c, change["row_key"]), json=_first("keep_ours")).status_code \
        == 201
    row = api.get(f"{_url(c)}/review-table").json()["data"]["rows"][0]
    assert row[6] == row[2] and row[7].startswith("Keep our wording")

    r = api.post(f"{_url(c)}/review-table/export")
    assert r.status_code == 200 and r.content[:2] == b"PK"
    assert db.scalar(select(func.count()).select_from(M.AuditEvent).where(
        M.AuditEvent.action == audit.REPORT_EXPORTED,
        M.AuditEvent.entity_id == c.id)) == 1
    stranger = _contract(db, make_user(db))
    _pair(db, stranger, "9. A.", "9. B.")
    assert api.get(f"{_url(stranger)}/review-table").status_code == 404
    assert api.post(f"{_url(stranger)}/review-table/export").status_code == 404


def test_a_point_on_our_own_unchanged_text_is_labelled_already_ours(db, owner):
    """Step 0: a point that fires on text we sent unchanged is "already in our MSA";
    a point on a clause the client changed is the client's (display only)."""
    from legalmind.api import angles
    from legalmind.mapping.service import load_clauses
    c = _contract(db, owner)
    rows = [("8", "Payment", "8. The Customer shall pay within 5 days."),
            (*LIAB, "9. Liability is capped at 12 months.")]
    ours = _version(db, c, 1, rows)
    theirs = _version(db, c, 2, [rows[0], (*LIAB, "9. Liability is uncapped.")])
    ours.doc_metadata = {"version_role": "COMPANY_DRAFT"}
    theirs.doc_metadata = {"version_role": "CLIENT_MODIFIED"}
    review = _review(db, theirs, [(0, E.FindingClassification.DEVIATION,
                                   E.RuleOutcome.UNACCEPTABLE),
                                  (1, E.FindingClassification.DEVIATION,
                                   E.RuleOutcome.UNACCEPTABLE)])
    for ev in db.scalars(select(M.EvaluationEvidence).join(
            M.Evaluation, M.Evaluation.id == M.EvaluationEvidence.evaluation_id)
            .join(M.Finding, M.Finding.id == M.Evaluation.finding_id)
            .where(M.Finding.review_id == review.id)):      # the roll-up, as evaluated
        db.add(M.FindingEvidence(finding_id=db.get(M.Evaluation, ev.evaluation_id)
                                 .finding_id, evidence_id=ev.evidence_id,
                                 relationship_type=ev.relationship_type))
    db.flush()
    got, _ = angles._origins(db, review, load_clauses(db, theirs.id),
                             angles._rows(db, review))
    by_clause = {r["sections"][0]: got[str(r["finding"].id)]
                 for r in angles._rows(db, review)}
    assert by_clause == {"8": "ALREADY_OURS", "9": "CLIENT_CHANGED"}


# ------------------------------------------ batch 8 (AB-222): what the client did not mark
def _lit(t: str) -> str:
    """A run the client highlighted (`legalmind-ingest-v13`)."""
    return (f'<w:r {W}><w:rPr><w:highlight w:val="yellow"/></w:rPr>'
            f'<w:t xml:space="preserve">{t}</w:t></w:r>')


def _round(db, owner, tmp_path, *theirs):
    c = _contract(db, owner)
    ours = _ingest(db, tmp_path, c, _docx(*OURS), "ours.docx")
    after = _ingest(db, tmp_path, c, _docx(*theirs), "theirs.docx")
    return c, ours, after, negotiation.changes(db, c, ours, after, legal_position=True)


def _row(listed, number):
    return next(r for r in listed["changes"] if r["clause"]["number"] == number)


def test_an_untracked_change_fully_highlighted_is_not_unmarked(db, owner, tmp_path):
    """R2.3/Q3: words the client ADDED and highlighted were marked — by the highlight."""
    *_, listed = _round(db, owner, tmp_path, OURS[0], [
        _run("2. This Agreement is governed by the laws of India"),
        _lit(" and of Singapore"), _run(".")], *OURS[2:])
    row = _row(listed, "2")
    assert row["untracked"] is True and row["unmarked"] is False
    assert listed["summary"]["unmarked"] == 0 and listed["summary"]["untracked"] == 1
    assert listed["summary"]["highlights_read"] is True


def test_an_untracked_deletion_is_unmarked_even_beside_a_highlight(db, owner, tmp_path):
    """A word of ours removed or replaced can never be marked by a highlight."""
    *_, listed = _round(db, owner, tmp_path, OURS[0], [
        _run("2. This Agreement is governed by the laws of "), _lit("Singapore"), _run(".")],
        OURS[2], "4. The Term is one year.")
    assert _row(listed, "2")["unmarked"] is True       # India -> Singapore, lit
    assert _row(listed, "4")["unmarked"] is True       # words deleted, nothing lit
    assert listed["summary"]["unmarked"] == 2


def test_a_partly_highlighted_untracked_change_is_unmarked(db, owner, tmp_path):
    *_, listed = _round(db, owner, tmp_path, OURS[0], [
        _run("2. This Agreement and every order is governed by the laws of India"),
        _lit(" and of Singapore"), _run(".")], *OURS[2:])
    assert _row(listed, "2")["unmarked"] is True       # "and every order" is not lit


def test_tracked_only_rows_are_never_unmarked(db, owner, tmp_path):
    *_, listed = _round(db, owner, tmp_path, [
        _run("1. Fees are payable within "), _mark("del", "30", 1), _mark("ins", "60", 2),
        _run(" days of invoice.")], *OURS[1:])
    [row] = listed["changes"]
    assert (row["tracked"], row["untracked"], row["unmarked"]) == (True, False, False)


def test_a_v12_client_version_says_highlights_not_read(db, owner, tmp_path):
    """A file read before v13 has no highlight data: the list says so, never "nothing
    was highlighted", and a v12/v13 pair is not re-read (one structure)."""
    from legalmind.analysis import reader_generation
    c, ours, after, _ = _round(db, owner, tmp_path, OURS[0],
                               "2. This Agreement is governed by the laws of Singapore.",
                               *OURS[2:])
    run = db.scalars(select(M.DocumentProcessingRun).where(
        M.DocumentProcessingRun.document_version_id == after.id)).one()
    run.processor_version = "legalmind-ingest-v12"
    db.flush()
    listed = negotiation.changes(db, c, ours, after, legal_position=True)
    assert listed["summary"]["highlights_read"] is False
    assert reader_generation.older(db, ours.id, after.id) is None


def test_a_table_comment_shows_on_its_change_row(db, owner, tmp_path):
    """R3a: the client's comment in a signature-table cell rides on that row."""
    import re

    from tests.test_docx_reading import _IN_CELL, _with_comment
    c = _contract(db, owner)
    ours = _ingest(db, tmp_path, c, _with_comment(lambda doc: doc), "ours.docx")
    cell = _IN_CELL.replace("PLACEHOLDER", "TO BE DATED")
    after = _ingest(db, tmp_path, c, _with_comment(lambda doc: re.sub(
        r"<w:r>(?:(?!<w:r>).)*?PLACEHOLDER</w:t></w:r>", cell, doc, count=1)),
        "theirs.docx")
    [row] = negotiation.changes(db, c, ours, after, legal_position=True)["changes"]
    assert row["after"]["comments"] == [{"author": "x", "text": "Date of signing needed"}]


#: a clause with a table under it it does not introduce (batch 8 R3c)
_VENUE = [("9", "Disputes", "9. Disputes go to the courts at City A."),
          (None, None, "| Item | Qty |"), (None, None, "| Node | 4 |")]


def _venue_pair(db, owner, cls_row):
    c = _contract(db, owner)
    v1 = _version(db, c, 1, _VENUE)
    v2 = _version(db, c, 2, [*_VENUE[:2], (None, None, "| Node | 5 |")])
    v1.doc_metadata, v2.doc_metadata = ({"version_role": "COMPANY_DRAFT"},
                                        {"version_role": "CLIENT_MODIFIED"})
    db.flush()
    # our version gave the venue standard the same result (round 2 D1 b)
    code = f"VENUE-{uuid.uuid4().hex[:6]}"
    _review(db, v1, [(0, E.FindingClassification.DEVIATION, E.RuleOutcome.UNACCEPTABLE)],
            code=code)
    _review(db, v2, [(cls_row, E.FindingClassification.DEVIATION,
                      E.RuleOutcome.UNACCEPTABLE)], code=code)
    return negotiation.changes(db, c, v1, v2, legal_position=True)["changes"]


def test_a_deviation_on_an_unchanged_row_does_not_make_the_row_worse(db, owner):
    """R3c-2: the venue paragraph is ours word for word; only the table under it
    changed. Its deviation is REVIEW there — WORSE only on a row the client changed."""
    [row] = _venue_pair(db, owner, 0)
    assert row["kind"] == "MODIFIED" and row["measured"] == negotiation.REVIEW
    [changed] = _venue_pair(db, owner, 2)
    assert changed["measured"] == negotiation.WORSE


def test_route_is_unchanged_by_row_level_measurement(db, owner):
    """`AM-299` r1: `measured` is never a routing input — the row still goes to Legal."""
    [row] = _venue_pair(db, owner, 0)
    assert (row["route"], row["effect_for_us"]) == ("holder", negotiation.NEGATIVE)


def _headed(db, contract, number, rows):
    """A version of (number, title, text, heading) rows — the heading flag as the reader
    records it."""
    version = _version(db, contract, number, [r[:3] for r in rows])
    stored = db.scalars(select(M.DocumentEvidence).where(
        M.DocumentEvidence.document_version_id == version.id)
        .order_by(M.DocumentEvidence.start_offset)).all()
    for evidence, row in zip(stored, rows, strict=True):
        evidence.evidence_metadata = {"heading": True} if row[3] else {}
    version.doc_metadata = {"version_role": "COMPANY_DRAFT" if number == 1
                            else "CLIENT_MODIFIED"}
    db.flush()
    return version


FM = "Force Majeure"
NO_LIABILITY = "No liability for delays due to events beyond control"
#: ours reads the body's first line as a heading too (a short Normal line); theirs,
#: restyled, reads only the title as one — R3d-2's case
OURS_FM = [("1", None, "1. Fees are payable monthly.", False), (None, FM, FM, True),
           (None, NO_LIABILITY, NO_LIABILITY, True),
           (None, None, "Includes floods and strikes.", False)]


def _fm(db, owner, *theirs):
    c = _contract(db, owner)
    v1, v2 = _headed(db, c, 1, OURS_FM), _headed(db, c, 2, list(theirs))
    return v1, v2, negotiation.changes(db, c, v1, v2, legal_position=True)["changes"]


def test_a_heading_reformatted_into_the_next_clause_is_not_deleted(db, owner):
    *_, rows = _fm(db, owner, OURS_FM[0], (None, FM, FM, True),
                   (None, None, NO_LIABILITY, False), OURS_FM[3])
    assert rows == []                     # the same words, only cut differently


def test_the_folded_row_keeps_its_key(db, owner, monkeypatch):
    """`AM-253`/`AM-433`: the folded row's key is the un-folded pair's, so an answer to
    it never detaches; the heading's DELETED row is gone."""
    theirs = (OURS_FM[0], (None, FM, FM, True), (None, None, NO_LIABILITY, False),
              (None, None, "Includes floods, strikes and pandemics.", False))
    v1, v2, rows = _fm(db, owner, *theirs)
    assert [r["kind"] for r in rows] == ["MODIFIED"]
    monkeypatch.setattr(negotiation, "fold_headings", lambda old, new, rows: rows)
    monkeypatch.setattr(negotiation, "_CORE", type(negotiation._CORE)())  # P2: rebuild
    c = db.get(M.Contract, v1.contract_id)
    unfolded = negotiation.changes(db, c, v1, v2, legal_position=True)["changes"]
    assert sorted(r["kind"] for r in unfolded) == ["DELETED", "MODIFIED"]
    assert rows[0]["row_key"] == next(r["row_key"] for r in unfolded
                                      if r["kind"] == "MODIFIED")
    assert rows[0]["before"]["text"].startswith(FM + "\n")      # heading + clause


def test_a_heading_really_deleted_still_shows(db, owner):
    *_, rows = _fm(db, owner, OURS_FM[0], (None, None, NO_LIABILITY, True), OURS_FM[3])
    assert [(r["kind"], r["before"]["text"]) for r in rows] == [("DELETED", FM)]


def test_a_dash_and_full_stop_change_is_punctuation_only_and_still_with_legal(db, owner):
    """R3d-1 / Q4: a dash and a dropped full stop are labelled, never routed past Legal."""
    c = _contract(db, owner)
    long = "9. The server has a shared port with a bandwidth of 8 mbps"
    v1, v2 = _pair(db, c, f"{long} - 30 mbps.", f"{long} \u2013 30 mbps")
    [row] = negotiation.changes(db, c, v1, v2, legal_position=True)["changes"]
    assert row["punctuation_only"] is True and row["route"] == "holder"
    v3, v4 = _pair(db, _contract(db, owner), "9. Bandwidth is 8 mbps.",
                   "9. Bandwidth is 9 mbps")
    [words] = negotiation.changes(db, db.get(M.Contract, v3.contract_id), v3, v4,
                                  legal_position=True)["changes"]
    assert "punctuation_only" not in words                    # omitted, never false


# ------------------------------------------------------------- batch 8 A, round 2
def test_a_carve_out_row_deleted_inside_a_unit_is_worse_and_client_changed(db, owner):
    """Round 2 D1 (rule 15): the client deleted our carve-out paragraph inside the
    liability clause. No row of theirs differs from ours, but the unit lost a row: every
    row of it is the client's change, so its deviation is WORSE and its point is
    CLIENT_CHANGED — never "already ours"."""
    from legalmind.analysis import lawyer_rows
    from legalmind.mapping.service import load_clauses
    c = _contract(db, owner)
    cap = "9. Liability is capped at the fees paid in the preceding twelve months."
    v1 = _version(db, c, 1, [(*LIAB, cap), (None, None, "The cap does not apply to fraud.")])
    v2 = _version(db, c, 2, [(*LIAB, cap)])
    v1.doc_metadata, v2.doc_metadata = ({"version_role": "COMPANY_DRAFT"},
                                        {"version_role": "CLIENT_MODIFIED"})
    db.flush()
    _review(db, v2, [(0, E.FindingClassification.DEVIATION, E.RuleOutcome.UNACCEPTABLE)])
    [row] = negotiation.changes(db, c, v1, v2, legal_position=True)["changes"]
    assert row["kind"] == "MODIFIED" and row["measured"] == negotiation.WORSE
    changed = lawyer_rows.changed_evidence(load_clauses(db, v1.id), load_clauses(db, v2.id))
    assert changed == set(row["after"]["evidence_ids"])
    assert lawyer_rows.origin(row["after"]["evidence_ids"], "X", "DEVIATION", changed,
                              {"X": "DEVIATION"}) == lawyer_rows.CLIENT_CHANGED


def test_an_unchanged_rows_deviation_is_review_only_where_ours_read_the_same():
    """Round 2 D1 (b): a deviation read only on rows the client left alone is REVIEW
    only when our version gave that standard the same result; else it stays WORSE."""
    after = [{"finding_id": "f", "requirement_code": "V", "classification": "DEVIATION",
              "user_status": "REQUIRES_MODIFICATION", "lower_cap_ours": False}]
    same = [{**after[0], "finding_id": "g"}]
    other = [{**same[0], "classification": "MATCH", "user_status": "ACCEPTABLE"}]
    measure = negotiation._measured
    assert measure(negotiation.NEGATIVE, "MODIFIED", same, after, None, set()) == {
        "measured": negotiation.REVIEW}
    assert measure(negotiation.NEGATIVE, "MODIFIED", other, after, None, set()) == {
        "measured": negotiation.WORSE}
    assert measure(negotiation.NEGATIVE, "MODIFIED", [], after, None, set()) == {
        "measured": negotiation.WORSE}


def test_a_joined_word_is_never_only_punctuation(db, owner):
    """Round 2 D4: the label is `same_words` (`AM-321` r2), not "the same letters". A
    joined word ("of Confidential" -> "ofConfidential") is never labelled punctuation
    only, and neither is a figure whose separator moved ("1,000" -> "1.000"), which
    keeps every letter and digit."""
    long = "9. Each Party shall protect the other Party's records of Confidential"
    for before, after in ((f"{long} Information.",
                           long.replace("of Confidential", "ofConfidential")
                           + " Information."),
                          (f"{long} Information worth Rs. 1,000 each.",
                           f"{long} Information worth Rs. 1.000 each.")):
        c = _contract(db, owner)
        v1, v2 = _pair(db, c, before, after)
        rows = negotiation.changes(db, c, v1, v2, legal_position=True)["changes"]
        assert not any("punctuation_only" in r for r in rows), (before, rows)
    assert rows and rows[0]["kind"] == "MODIFIED"                 # the figure is a row


def test_a_typography_change_on_a_measured_clause_is_not_in_the_headline(db, owner):
    """Round 2 D5: curly quotes made straight on a clause a standard measures — still a
    holder's row (measured), tagged, but not one of the "not marked" changes."""
    c = _contract(db, owner)
    v1, v2 = _pair(db, c, "9. The Customer\u2019s liability \u2014 capped at fees paid.",
                   "9. The Customer's liability - capped at fees paid.")
    _review(db, v2, [(0, E.FindingClassification.DEVIATION, E.RuleOutcome.UNACCEPTABLE)])
    listed = negotiation.changes(db, c, v1, v2, legal_position=True)
    [row] = listed["changes"]
    assert row["route"] == "holder" and row["typography_only"] is True
    assert row["unmarked"] is True and listed["summary"]["unmarked"] == 0


# ------------------------------------------------------- round 3: a carve-out rewritten
CAP9 = "9. Liability is capped at the fees of twelve months."
CARVE = "The cap does not apply to the Customer's payment obligations."
MITIGATE = "Each party must mitigate its loss."


@pytest.mark.parametrize("theirs", [
    # replaced 1 -> 1 by an unrelated row
    [CAP9, "Liability for data loss is limited to restoring the last backup.", MITIGATE],
    # reworded to weaken it
    [CAP9, "The cap applies to the Customer's payment obligations.", MITIGATE],
    # split in two, a word changed in the split
    [CAP9, "The cap does not apply", "to payment obligations.", MITIGATE],
], ids=["replaced", "weakened", "split"])
def test_a_carve_out_rewritten_in_place_is_the_whole_clauses_change(theirs):
    """Round 3 (rule 15): a prose row of ours rewritten in place is the whole clause's
    change, as a deletion is — a point reading only the unchanged cap row is never
    "already ours", and a deviation there is never only "review"."""
    from legalmind.analysis import lawyer_rows
    from legalmind.mapping.engine import Clause
    ours = [Clause(uuid.uuid4(), t, "9" if t.startswith("9.") else None)
            for t in (CAP9, CARVE, MITIGATE)]
    new = [Clause(uuid.uuid4(), t, "9" if t.startswith("9.") else None) for t in theirs]
    [o], [n] = negotiation._units(ours), negotiation._units(new)
    assert negotiation.changed_rows(o, n) == n["evidence_ids"]
    changed = lawyer_rows.changed_evidence(ours, new)
    cap = [str(new[0].evidence_id)]
    assert lawyer_rows.origin(cap, "LIAB", "DEVIATION", changed, None) \
        == lawyer_rows.CLIENT_CHANGED
    dev = {"finding_id": "F1", "requirement_code": "LIAB", "classification": "DEVIATION",
           "user_status": "REQUIRES_MODIFICATION", "lower_cap_ours": False}
    on_changed = {"F1"} if cap[0] in negotiation.changed_rows(o, n) else set()
    assert negotiation._measured(negotiation.NEGATIVE, "MODIFIED", [{**dev,
                                 "finding_id": "F0"}], [dev], None, on_changed) == {
        "measured": negotiation.WORSE}


def test_a_table_row_rewritten_alone_is_still_row_by_row():
    """R3c holds: only a price-table row rewritten — that row alone is the client's."""
    from legalmind.mapping.engine import Clause
    ours = [Clause(uuid.uuid4(), t, "9" if t.startswith("9.") else None)
            for t in (CAP9, "| Node | Qty |", "| GPU | 4 |")]
    new = [Clause(uuid.uuid4(), t, "9" if t.startswith("9.") else None)
           for t in (CAP9, "| Node | Qty |", "| GPU | 5 |")]
    [o], [n] = negotiation._units(ours), negotiation._units(new)
    assert negotiation.changed_rows(o, n) == [str(new[2].evidence_id)]


# ------------------------------------------- round 4: one fail-closed rule for every span
_BREACH = "The cap shall not apply to LeapSwitch's liability for any data breach."


@pytest.mark.parametrize(("ours", "theirs"), [
    ((CAP9, MITIGATE), (CAP9, _BREACH, MITIGATE)),                  # inserted, middle
    ((CAP9, MITIGATE), (CAP9, MITIGATE, _BREACH)),                  # inserted, end
    ((CAP9, "| Node | 4 |"), (CAP9, "The cap does not apply to any node.")),  # table->prose
], ids=["inserted-middle", "inserted-end", "table-row-to-prose"])
def test_a_prose_row_inserted_or_put_in_a_tables_place_is_the_whole_clauses_change(
        ours, theirs):
    """Round 4 (rule 15, the case's own lesson R2): a carve-out the client INSERTS into
    our clause, or prose put where our table row was, is the whole clause's change — a
    point on our unchanged cap is never "already ours", nor only "review"."""
    from legalmind.analysis import lawyer_rows
    from legalmind.mapping.engine import Clause
    def rows(texts):
        return [Clause(uuid.uuid4(), t, "9" if t.startswith("9.") else None) for t in texts]
    o_rows, n_rows = rows(ours), rows(theirs)
    [o], [n] = negotiation._units(o_rows), negotiation._units(n_rows)
    assert negotiation.changed_rows(o, n) == n["evidence_ids"]
    changed = lawyer_rows.changed_evidence(o_rows, n_rows)
    cap = [str(n_rows[0].evidence_id)]
    assert lawyer_rows.origin(cap, "LIAB", "DEVIATION", changed, None) \
        == lawyer_rows.CLIENT_CHANGED                            # no review of ours
    dev = {"finding_id": "F1", "requirement_code": "LIAB", "classification": "DEVIATION",
           "user_status": "REQUIRES_MODIFICATION", "lower_cap_ours": False}
    assert negotiation._measured(negotiation.NEGATIVE, "MODIFIED", [{**dev,
                                 "finding_id": "F0"}], [dev], None, {"F1"}) == {
        "measured": negotiation.WORSE}                          # ours already DEVIATION


def test_a_title_line_added_beside_a_rewritten_table_stays_row_by_row():
    """Round 4: a short title line ("Legal Terms & Conditions:") the client added beside
    a rewritten price table is no prose change — the clause above is still ours (R3c)."""
    from legalmind.mapping.engine import Clause
    ours = [Clause(uuid.uuid4(), t, "9" if t.startswith("9.") else None)
            for t in (CAP9, "| GPU | 4 |")]
    new = [Clause(uuid.uuid4(), t, "9" if t.startswith("9.") else None)
           for t in (CAP9, "| GPU | 5 |", "Legal Terms & Conditions:")]
    [o], [n] = negotiation._units(ours), negotiation._units(new)
    assert negotiation.changed_rows(o, n) == [str(new[1].evidence_id),
                                              str(new[2].evidence_id)]


def test_a_short_untitled_line_is_never_a_title():
    """A carve-out inserted without a full stop is prose, not a title: only a colon
    lead-in or a Title Case line is read row by row (batch 8 R3c, fail closed)."""
    from legalmind.analysis.negotiation import _row_by_row

    assert _row_by_row("Legal Terms & Conditions:")
    assert _row_by_row("Limitation of Liability")
    assert _row_by_row("| GPUN-1 | 4 | 29,98,400 |")
    assert not _row_by_row("except for data breaches")
    assert not _row_by_row("The cap does not apply to data breach")
    assert not _row_by_row("The cap does not apply.")
