"""Batch 5 (AB-221, `AM-455`–`AM-460`): our own contract came back marked up.

A returned Word file is compared with the copy we sent when we hold it; when we do not,
the upload declares ``X-Compare-With: TRACKED_ORIGINAL`` and the file is compared with its
own text before the client's tracked changes — a virtual side, never stored, never ours,
never an opening, with "Keep ours" withheld until Legal says it may go back as ours (Q2).

Every document is built here as synthetic OOXML (CI runs it without any real file) and
names no client; the words are illustrations, never a position (rule 21). The one real
file is read by test 12 only, structurally, when the source material is present.
"""

from __future__ import annotations

import io
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import docx
import pytest
from sqlalchemy import func, select

from legalmind import notifications
from legalmind.analysis import negotiation
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.drafting import blank
from legalmind.drafting import playbook as read
from legalmind.drafting.reply_docx import apply_reply
from legalmind.drafting.reply_plan import Answer, reply_rows
from legalmind.ingestion.parsing import parse_docx
from legalmind.ingestion.service import ingest_document
from legalmind.mapping.service import load_clauses
from legalmind.security import audit
from legalmind.security import permissions as P
from tests.conftest import grant_role, make_user, sign_in
from tests.test_negotiation import OURS, _contract, owner  # noqa: F401
from tests.test_redline_truth import EDITED, build, d, gone, i, p, plain, r
from tests.test_version_comparison import V1

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
ADDED = "5. The Customer may assign this Agreement freely."
#: clause 1 edited under marks, clause 3 deleted whole (it rides on clause 2), clause 4
#: untouched with a Word comment, clause 5 inserted under a mark
RETURNED = build(EDITED, p(r(OURS[1])), gone(OURS[2], 3), p(r(OURS[3])), p(i(ADDED, 7)),
                 comment_on=3, comment="Please confirm.")
TRACKED = {"X-Compare-With": "TRACKED_ORIGINAL"}


def _upload(api, contract, data=RETURNED, role="CLIENT_MODIFIED", mime=DOCX,
            name="returned.docx", headers=None):
    return api.post(f"{V1}/contracts/{contract.id}/document-versions", content=data,
                    headers={"Content-Type": mime, "X-Version-Role": role,
                             "X-Filename": name, **(headers or {})})


def _tracked_deal(api, db, owner):
    """A new deal whose first version is the returned file, declared tracked-only."""
    c = _contract(db, owner)
    r_ = _upload(api, c, headers=TRACKED)
    assert r_.status_code == 201, r_.text
    return c, db.get(M.DocumentVersion, uuid.UUID(r_.json()["data"]["document_version"]["id"]))


def _changes(api, contract):
    got = api.get(f"{V1}/contracts/{contract.id}/changes")
    assert got.status_code == 200, got.text
    return got.json()["data"]


def _rows(listed):
    return [(c["kind"], c["clause"]["number"]) for c in listed["changes"]]


def _holder(db, owner):
    """A Legal Decision holder in the owner's department, who may answer an unmeasured
    change with a reason (`AM-281`) — the tracked-only rows have no Review here."""
    team = M.Department(code=f"T{uuid.uuid4().hex[:6]}", name="Team")
    db.add(team)
    db.flush()
    holder = make_user(db)
    grant_role(db, holder, P.ROLE_DEPARTMENT_LEAD)
    grant_role(db, holder, P.ROLE_LEGAL_DECISION_AUTHORITY)
    owner.department_id = holder.department_id = team.id
    db.flush()
    return holder


def _accept(api, contract, change, **extra):
    r_ = api.post(f"{V1}/contracts/{contract.id}/changes/"
                  f"{change['row_key'].replace('|', '%7C')}/answers",
                  json={"answer": "accept_theirs", "reason": "fine for us",
                        "expected_version": 0, **extra})
    assert r_.status_code == 201, r_.text
    return r_


@pytest.fixture
def snapshot(db, owner):
    """A published (empty) configuration, so a prepared reply is reviewed (`AM-251` r4)."""
    db.add(M.ConfigurationSnapshot(snapshot_hash=uuid.uuid4().hex, created_by=owner.id,
                                   created_at=datetime.now(UTC) - timedelta(days=1)))
    db.flush()


# ---------------------------------------------------------------- 1–3 the rows
def test_tracked_only_rows_are_exactly_the_marked_clauses(api, db, owner):
    """Clause 1 edited and clause 5 inserted under marks, clause 3 deleted whole: exactly
    the marked units are rows. The deleted paragraph is kept on the row before it by the
    reader (`parsing.drop`), so it shows on clause 2 (SPEC risk, accepted); clause 4 —
    unmarked, only commented — is no row, its comment rides in ``comments_elsewhere``."""
    c, _ = _tracked_deal(api, db, owner)
    listed = _changes(api, c)
    assert _rows(listed) == [("MODIFIED", "1"), ("MODIFIED", "2"), ("ADDED", "5")]
    two = listed["changes"][1]
    assert OURS[2] in two["before"]["text"] and OURS[2] not in two["after"]["text"]
    assert [e["text"] for e in listed["comments_elsewhere"]] == ["Please confirm."]


def test_tracked_only_never_reports_untracked(api, db, owner):
    c, _ = _tracked_deal(api, db, owner)
    listed = _changes(api, c)
    assert listed["summary"]["untracked"] == 0
    assert all(ch["untracked"] is False and ch["tracked"] for ch in listed["changes"])
    assert listed["tracked_base"] is True
    assert "template" not in listed and listed["from"] is None       # omitted, not nulled


def test_tracked_base_rows_are_never_unmarked(api, db, owner):
    """Batch 8 R2.3 (`AM-457`): our side IS their text before the marks, so no change on
    the tracked-only base can be "not marked" — and the brief says nothing about it."""
    c, _ = _tracked_deal(api, db, owner)
    listed = _changes(api, c)
    assert listed["summary"]["unmarked"] == 0
    assert not any(ch["unmarked"] for ch in listed["changes"])
    brief = api.get(f"{V1}/contracts/{c.id}/brief")
    assert brief.status_code == 200 and "not_marked" not in brief.json()["data"]


def test_tracked_only_keys_stable_and_answers_survive(api, db, owner):
    """`AM-253`/`AM-433`: the same keys on every read; an answer stored with the left key
    ``tracked:<version>`` (the CHECK holds) is read back on reload (review M1)."""
    c, v = _tracked_deal(api, db, owner)
    first = _changes(api, c)
    assert [ch["row_key"] for ch in first["changes"]] == \
        [ch["row_key"] for ch in _changes(api, c)["changes"]]
    assert {ch["anchor"]["left_key"] for ch in first["changes"]} == {f"tracked:{v.id}"}
    holder = _holder(db, owner)
    sign_in(api, db, holder)
    _accept(api, c, first["changes"][0])
    sign_in(api, db, owner)
    again = _changes(api, c)
    assert again["changes"][0]["answer"]["answer"] == "accept_theirs"
    assert [ch["answer"] for ch in again["changes"][1:]] == [None, None]
    stored = db.execute(select(M.ComparisonChoice)).scalars().one()
    assert (stored.left_version_id, stored.left_key) == (None, f"tracked:{v.id}")


# ---------------------------------------------------------------- 4 never ours
def test_tracked_only_is_never_ours(api, db, owner, monkeypatch):
    c, v = _tracked_deal(api, db, owner)
    versions = db.execute(select(M.DocumentVersion).where(
        M.DocumentVersion.contract_id == c.id)).scalars().all()
    assert versions == [v] and not negotiation.is_ours(v)
    assert all((x.doc_metadata or {}).get("version_role") != "COMPANY_DRAFT"
               for x in versions)
    opened = _openings(db, c, monkeypatch)
    assert opened == [False]                         # AM-317 r4: at the standard
    plan = api.get(f"{V1}/contracts/{c.id}/package").json()["data"]
    assert [b["code"] for b in plan["blockers"]] == ["NOT_OUR_TEMPLATE"]
    convert = api.post(f"{V1}/contracts/{c.id}/convert/preview",
                       json={"draft_id": str(uuid.uuid4())}).json()["data"]
    assert convert["blockers"] == [{
        "code": "NOT_CLIENT_PAPER", "message": "This is our own contract, marked up by "
        "the client — answer its changes instead."}]


def _openings(db, contract, monkeypatch) -> list[bool]:
    """How `playbook.for_contract` builds the playbook: openings at our paper or not."""
    seen: list[bool] = []

    def spy(*_a, **kw):
        seen.append(kw.get("openings", True))
        return []
    monkeypatch.setattr(read, "from_review", spy)
    read.for_contract(db, contract)
    return seen


def test_only_our_real_drafts_supply_openings(api, db, owner, snapshot, monkeypatch):
    """Owner 2026-11-23 (`AM-458`): a reply LegalMind prepared is ours by role but never
    our draft — after "Prepare reply" a tracked-only deal, and a deal on the client's own
    paper, still open at the standard; a real draft of ours still opens at our paper."""
    monkeypatch.delenv("LEGALMIND_SOFFICE", raising=False)
    c, _ = _tracked_deal(api, db, owner)
    holder = _holder(db, owner)
    sign_in(api, db, holder)
    for change in _changes(api, c)["changes"]:
        _accept(api, c, change)
    sign_in(api, db, owner)
    reply = api.post(f"{V1}/contracts/{c.id}/reply")
    assert reply.status_code == 201, reply.text
    made = db.get(M.DocumentVersion,
                  uuid.UUID(reply.json()["data"]["document_version"]["id"]))
    assert made.doc_metadata["version_role"] == "COMPANY_DRAFT" and made.doc_metadata[
        "reply_to"]
    assert _openings(db, c, monkeypatch) == [False]

    # client paper first, then the reply LegalMind prepared on it (its markers, as
    # `prepare_reply` writes them); and a real draft of ours, which opens at our paper
    paper, ours = _contract(db, owner), _contract(db, owner)
    for contract, n, meta in ((paper, 1, {"version_role": "CLIENT_MODIFIED"}),
                              (paper, 2, {"version_role": "COMPANY_DRAFT", "reply_to": "x"}),
                              (ours, 1, {"version_role": "COMPANY_DRAFT"})):
        db.add(M.DocumentVersion(contract_id=contract.id, version_number=n,
                                 original_filename=f"v{n}.docx", mime_type=DOCX,
                                 file_size_bytes=1, file_hash=f"h{n}", storage_key=f"k{n}",
                                 processing_status=E.ProcessingStatus.COMPLETED,
                                 uploaded_by=owner.id, doc_metadata=meta))
    db.flush()
    assert _openings(db, paper, monkeypatch) == [False]
    assert _openings(db, ours, monkeypatch) == [True]


def test_a_flagged_version_is_never_recast_as_ours(api, db, owner):
    """Review M2: PATCHing whose paper it is, before any Review, is refused (409)."""
    _, v = _tracked_deal(api, db, owner)
    for body in ({"version_role": "COMPANY_DRAFT"}, {"source": "ORGANIZATION"}):
        r_ = api.patch(f"{V1}/document-versions/{v.id}", json=body)
        assert r_.status_code == 409, r_.text
    assert v.doc_metadata["version_role"] == "CLIENT_MODIFIED"


# ---------------------------------------------------------------- 6–7, 10–11 the upload
def _notices(db, contract):
    return db.scalar(select(func.count()).select_from(M.Notification).where(
        M.Notification.contract_id == contract.id))


def _uploaded(db, contract):
    return db.scalar(select(func.count()).select_from(M.AuditEvent).where(
        M.AuditEvent.action == audit.DOCUMENT_UPLOADED, M.AuditEvent.entity_id == contract.id))


@pytest.mark.parametrize(("case", "code"), [
    ("company_draft", "BUSINESS_RULE_REJECTED"),
    ("second_version", "BUSINESS_RULE_REJECTED"),
    ("pdf", "WORD_FILE_NEEDED"),
    ("clean_docx", "NO_TRACKED_CHANGES"),
    ("unknown_value", "BUSINESS_RULE_REJECTED"),
])
def test_compare_with_refusals_keep_nothing(api, db, owner, tmp_path, case, code):
    c = _contract(db, owner)
    if case == "second_version":
        assert _upload(api, c, data=plain(*OURS), role="COMPANY_DRAFT").status_code == 201
    before = (_versions(db, c), _notices(db, c), _uploaded(db, c))
    stored = _stored(tmp_path)
    r_ = _upload(api, c, **{
        "company_draft": {"role": "COMPANY_DRAFT", "headers": TRACKED},
        "second_version": {"headers": TRACKED},
        "pdf": {"data": b"%PDF-1.4 synthetic", "mime": "application/pdf",
                "name": "returned.pdf", "headers": TRACKED},
        "clean_docx": {"data": plain(*OURS), "headers": TRACKED},
        "unknown_value": {"headers": {"X-Compare-With": "TEMPLATE"}},
    }[case])
    assert r_.status_code == 422, r_.text
    assert r_.json()["error"]["code"] == code
    assert (_versions(db, c), _notices(db, c), _uploaded(db, c)) == before
    assert _stored(tmp_path) == stored             # the refused bytes are not kept


def _versions(db, contract):
    return db.scalar(select(func.count()).select_from(M.DocumentVersion).where(
        M.DocumentVersion.contract_id == contract.id))


def _stored(tmp_path) -> int:
    return sum(1 for f in (tmp_path / "objects").rglob("*") if f.is_file())


def test_one_notice_per_returned_upload(api, db, owner):
    """R7: a collaborator's (b) path — the copy we sent, then the returned file — tells
    the owner once; the (c) path once too. The copy we sent tells nobody."""
    team = M.Department(code=f"T{uuid.uuid4().hex[:6]}", name="Team")
    db.add(team)
    db.flush()
    mate = make_user(db)
    grant_role(db, mate, P.ROLE_USER)
    owner.department_id = mate.department_id = team.id
    with_copy, tracked_only = _contract(db, owner), _contract(db, owner)
    for c in (with_copy, tracked_only):
        db.add(M.ContractCollaborator(contract_id=c.id, user_id=mate.id, added_by=owner.id))
    db.flush()
    sign_in(api, db, mate)
    assert _upload(api, with_copy, data=plain(*OURS), role="COMPANY_DRAFT").status_code == 201
    assert _notices(db, with_copy) == 0
    assert _upload(api, with_copy).status_code == 201
    assert _upload(api, tracked_only, headers=TRACKED).status_code == 201
    for c in (with_copy, tracked_only):
        assert db.execute(select(M.Notification.user_id, M.Notification.kind).where(
            M.Notification.contract_id == c.id)).all() == [
            (owner.id, notifications.CLIENT_RETURNED)]


def test_what_we_sent_then_returned_pairs_and_sees_silent_edits(api, db, owner):
    """(b): v1 the copy we sent, v2 the client's file with one tracked and one silent edit
    — compared with v1, and exactly the silent edit is untracked (the negative control)."""
    c = _contract(db, owner)
    assert _upload(api, c, data=plain(*OURS), role="COMPANY_DRAFT").status_code == 201
    silent = build(EDITED, p(r("2. This Agreement is governed by the laws of Singapore.")),
                   p(r(OURS[2])), p(r(OURS[3])))
    assert _upload(api, c, data=silent).status_code == 201
    listed = _changes(api, c)
    assert listed["from"]["version_number"] == 1 and "tracked_base" not in listed
    assert [(ch["clause"]["number"], ch["untracked"]) for ch in listed["changes"]] == [
        ("1", False), ("2", True)]
    assert listed["summary"]["untracked"] == 1


def test_out_of_scope_upload_is_byte_identical_404(api, db, owner):
    other = make_user(db)
    grant_role(db, other, P.ROLE_USER)
    theirs = _contract(db, other)
    missing = M.Contract(id=uuid.uuid4(), owner_id=other.id, name="x")

    def body(r_):
        out = r_.json()
        out["error"]["request_id"] = "-"
        return r_.status_code, out
    seen = {repr(body(_upload(api, c, headers=h)))
            for c in (theirs, missing) for h in (None, TRACKED)}
    assert len(seen) == 1 and "404" in seen.pop()
    assert _versions(db, theirs) == 0


def test_upload_audit_names_compare_with(api, db, owner):
    c, v = _tracked_deal(api, db, owner)
    event = db.execute(select(M.AuditEvent).where(
        M.AuditEvent.action == audit.DOCUMENT_UPLOADED,
        M.AuditEvent.entity_id == c.id)).scalars().one()
    assert event.after_state["compare_with"] == "TRACKED_ORIGINAL"
    assert v.doc_metadata["compare_with"] == "TRACKED_ORIGINAL"


# ---------------------------------------------------------------- 8 the reply
def test_reply_on_tracked_only_rejects_the_change(api, db, owner, tmp_path):
    """Keep ours on a marked edit writes the words before the client's mark back as our
    tracked change; accept theirs leaves it; a paragraph deleted whole is left to a person
    (review M6). Until Legal answers Q2, "Keep ours" is never offered here and the server
    refuses it (review M5)."""
    c, v = _tracked_deal(api, db, owner)
    listed = _changes(api, c)
    assert all("keep_ours" not in ch["offers"] for ch in listed["changes"])
    one, two, five = listed["changes"]
    refused = api.post(f"{V1}/contracts/{c.id}/changes/"
                       f"{one['row_key'].replace('|', '%7C')}/answers",
                       json={"answer": "keep_ours", "expected_version": 0})
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "NOTHING_OF_OURS"
    bulk = api.post(f"{V1}/contracts/{c.id}/changes/formatting/keep-ours",
                    json={"row_keys": [one["row_key"]]})
    assert bulk.status_code == 409

    template = blank.base(db, c, v)
    plans = reply_rows(db, None, v, {one["row_key"]: Answer("keep_ours"),
                                     two["row_key"]: Answer("keep_ours"),
                                     five["row_key"]: Answer("accept_theirs")},
                       RETURNED, template=template)
    by = {p_.row_key: p_ for p_ in plans}
    assert by[one["row_key"]].error is None and by[one["row_key"]].edits
    assert by[two["row_key"]].error is not None \
        and by[two["row_key"]].error.code == "UNSUPPORTED"         # restored by hand
    reply = apply_reply(RETURNED, by[one["row_key"]].edits, when=datetime.now(UTC))
    text = [s.content for s in parse_docx(reply).segments]
    assert text[0] == OURS[0] and ADDED in text                     # 60 -> 30; 5 stays


# ---------------------------------------------------------------- S1 the deal list
def test_the_deal_list_names_the_deals_i_may_answer(api, db, owner):
    """Review S1: ``scope=negotiable`` lists mine and a colleague's I collaborate on (in
    the owner's department) — never a deal I may not upload to."""
    team = M.Department(code=f"T{uuid.uuid4().hex[:6]}", name="Team")
    db.add(team)
    db.flush()
    colleague, stranger = make_user(db), make_user(db)
    owner.department_id = colleague.department_id = team.id
    db.flush()
    mine, shared, other = (_contract(db, owner), _contract(db, colleague),
                           _contract(db, stranger))
    db.add(M.ContractCollaborator(contract_id=shared.id, user_id=owner.id,
                                  added_by=colleague.id))
    db.flush()
    listed = api.get(f"{V1}/contracts", params={"scope": "negotiable"})
    assert listed.status_code == 200, listed.text
    ids = {row["id"] for row in listed.json()["data"]}
    assert {str(mine.id), str(shared.id)} <= ids and str(other.id) not in ids
    own = {row["id"] for row in api.get(f"{V1}/contracts").json()["data"]}
    assert str(shared.id) not in own                              # `own` is unchanged


# ---------------------------------------------------------------- 12 the real file
_CASES = Path(os.environ.get("LEGALMIND_SOURCE_MATERIAL_DIR", "/nonexistent")) / "cases"


class _Memory:
    """Storage in memory: the real file is read, never copied to disk."""

    def __init__(self):
        self.held: dict[str, bytes] = {}

    def put(self, data, *, suggested_name):
        key = uuid.uuid4().hex
        self.held[key] = data
        return key

    def get(self, key):
        return self.held[key]


def _marked(path: Path) -> bool:
    return any(s.metadata.get("revision") for s in parse_docx(path.read_bytes()).segments)


@pytest.mark.skipif(not _CASES.is_dir(), reason="source material not provisioned")
def test_real_case_tracked_only_rows_match_marked_units(db, owner):
    """The real-file gate (structural only: no text asserted, no file copied): every
    returned Word file with tracked changes gives one row per marked unit, nothing
    untracked, unique keys, and every comment on a row or in ``comments_elsewhere``."""
    files = [f for f in sorted(_CASES.glob("*/*.docx")) if _marked(f)]       # N6
    if not files:
        pytest.skip("no returned Word file with tracked changes in the source material")
    for path in files:
        c = _contract(db, owner)
        v = ingest_document(db, _Memory(), contract_id=c.id, uploaded_by=owner.id,
                            data=path.read_bytes(), filename="returned.docx",
                            declared_mime=DOCX).document_version
        v.doc_metadata = {**(v.doc_metadata or {}), "version_role": "CLIENT_MODIFIED",
                          "compare_with": "TRACKED_ORIGINAL"}
        db.flush()
        listed = negotiation.changes(db, c, None, v, legal_position=True,
                                     template=blank.base(db, c, v))
        units = negotiation._units(load_clauses(db, v.id))
        marked = [u for u in units if u["changes"]]
        keys = [ch["row_key"] for ch in listed["changes"]]
        assert len(keys) == len(marked) and len(set(keys)) == len(keys)
        assert listed["summary"]["untracked"] == 0
        comments = sum(len(u["comments"]) for u in units)
        on_rows = sum(len((ch["after"] or {}).get("comments", ())) for ch in listed["changes"])
        assert on_rows + len(listed.get("comments_elsewhere", ())) == comments


# ---------------------------------------------------------------- round 2
def test_a_mark_on_page_furniture_only_is_no_tracked_change(api, db, owner, monkeypatch):
    """Verifier (outside the spec): a mark on page furniture (a contents line keeps its
    paragraph's revision; a header or footer) is not the client's change to the contract —
    the file is still refused NO_TRACKED_CHANGES. The footer row is given the revision
    after the read, as a contents row carries it."""
    from legalmind.api.routers import contracts as route

    def marked(*a, **kw):
        result = real(*a, **kw)
        for e in db.execute(select(M.DocumentEvidence).where(
                M.DocumentEvidence.processing_run_id == result.processing_run.id)).scalars():
            if (e.evidence_metadata or {}).get("part") == "footer":
                e.evidence_metadata = {**e.evidence_metadata, "revision": {
                    "original": "Page", "changes": [{"deleted": "", "inserted": " 2"}]}}
        db.flush()
        return result
    real = route.ingest_document
    monkeypatch.setattr(route, "ingest_document", marked)
    document = docx.Document(io.BytesIO(plain(*OURS)))
    footer = document.sections[0].footer
    footer.is_linked_to_previous = False
    footer.paragraphs[0].text = "Page 2"
    out = io.BytesIO()
    document.save(out)
    assert any(s.metadata.get("part") == "footer" for s in parse_docx(out.getvalue()).segments)
    c = _contract(db, owner)
    r_ = _upload(api, c, data=out.getvalue(), headers=TRACKED)
    assert r_.status_code == 422 and r_.json()["error"]["code"] == "NO_TRACKED_CHANGES"
    assert _versions(db, c) == 0


def test_accept_together_on_the_tracked_only_base(api, db, owner):
    """Review D1: "Accept all with no change for us" writes its rows with the base's left
    key (the `left_side` CHECK holds) and they read back after a reload."""
    c = _contract(db, owner)
    data = build(p(r("10. Fees are monthly"), d(",", 1), i(";", 2), r(" in arrears.")),
                 p(r("11. Notices by post.")))
    assert _upload(api, c, data=data, headers=TRACKED).status_code == 201
    [row] = _changes(api, c)["changes"]
    assert row["effect_for_us"] == "NEUTRAL" and row["route_reason"] == "FORMATTING_ONLY"
    done = api.post(f"{V1}/contracts/{c.id}/changes/accept",
                    json={"effect": "NEUTRAL", "row_keys": [row["row_key"]]})
    assert done.status_code == 201, done.text
    assert _changes(api, c)["changes"][0]["answer"]["answer"] == "accept_theirs"
    stored = db.execute(select(M.ComparisonChoice)).scalars().one()
    assert stored.left_key.startswith("tracked:") and stored.left_version_id is None
