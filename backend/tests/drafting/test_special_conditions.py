"""The Special Conditions annexure and the effective contract — `AM-307` (B1–B6).

The STRUCTURAL placeholder template and synthetic text only (rule 21). The frame and the
precedence clause are the DRAFT reference text (`config/templates/special_conditions/`),
approved here inside the test only — never seeded APPROVED.
"""

from __future__ import annotations

import copy
import io
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from docx.oxml.ns import qn
from sqlalchemy import select

from legalmind.analysis import effective, negotiation
from legalmind.analysis.service import run_analysis
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.drafting import library, preflight, special_conditions
from legalmind.drafting import model as model_
from legalmind.drafting import render_contract as R
from legalmind.ingestion.parsing import parse_docx
from legalmind.security import permissions as P
from tests.conftest import grant_role, make_user, sign_in
from tools import import_template as T

V1 = "/api/v1"


# ---------------------------------------------------------------- the model (no DB)
def _with_frame(placeholder):
    template, clauses = copy.deepcopy(placeholder)
    import json
    for c in json.loads(T.SPECIAL_REFERENCE.read_text())["clause_versions"]:
        row = T.check_clause(c)
        clauses[(row["clause_key"], row["version"])] = row
    template["clauses"].append({"clause_key": "SC.PRECEDENCE", "version": 1})
    cfg = {"frame": {"clause_key": "SC.FRAME", "version": 1},
           "precedence": "SC.PRECEDENCE", "position": "after_execution", "initials": True}
    template["layout"]["special_conditions"] = cfg
    return template, clauses, cfg


def _entries(base):
    t = special_conditions.targets(base)
    pub = special_conditions._public
    return [
        {"n": 1, "op": "replace", "target": pub(t["2.2"]),
         "text": "Clause A.2 agreed text.\nIts second paragraph."},
        {"n": 2, "op": "insert_after", "target": pub(t["4.2"]), "new_number": "4.2A",
         "text": "Inserted clause text."},
        {"n": 3, "op": "delete", "target": pub(t["5"]), "text": None}]


def test_without_special_conditions_the_model_and_bytes_are_unchanged(placeholder, answers):
    """Byte for byte what the renderer before `AM-307` (HEAD ca1d73ba) made — a fixture
    generated from that commit's code, not the new code compared with itself."""
    import hashlib
    import json
    baseline = json.loads((Path(__file__).parent / "render_baseline.json").read_text())
    template, clauses = placeholder
    plain = model_.resolve(template, clauses, answers)
    again = model_.resolve(template, clauses, answers, special={"entries": []})
    assert "special_conditions" not in again and plain == again
    assert model_.model_hash(plain) == baseline["model_hash"]
    docx = R.render(plain, template["assets"], contract_ref="T", version_number=1,
                    model_hash="0" * 64)
    assert hashlib.sha256(docx).hexdigest() == baseline["docx_sha256"]
    assert b"lm:special-conditions" not in docx


def test_the_annexure_is_a_new_section_numbered_and_cross_referenced(placeholder, answers):
    template, clauses, cfg = _with_frame(placeholder)
    base = model_.resolve(template, clauses, answers)
    frame = clauses[("SC.FRAME", 1)]
    m = model_.resolve(template, clauses, answers,
                       special={"frame": frame, "config": cfg, "entries": _entries(base)})
    sc = m["special_conditions"]
    assert [e["n"] for e in sc["entries"]] == ["1", "2", "3"]
    # 2.2 has no key of its own: a synthetic anchor, bookmarked only because it is named
    assert sc["anchors"] == {"CLAUSE_A~2.2": "2.2"}
    assert model_.text_of(sc["entries"][0]["lead"]) == \
        "Clause 2.2 is replaced by the following:"          # no title of its own
    assert model_.text_of(sc["entries"][1]["lead"]).startswith("A new Clause 4.2A is added")
    assert sc["entries"][2]["blocks"] == []
    assert model_.text_of(sc["title"]) == "Annexure A — Special Conditions"
    assert model_.text_of(sc["opening"][0]).startswith(
        "These Special Conditions form an integral part of the Placeholder dated "
        "1 January 2026 between Party One Placeholder Limited and Party Two "
        "Placeholder Private Limited.")
    assert sc["signature"] is True
    docx = R.render(m, template["assets"], contract_ref="T", version_number=2,
                    model_hash=model_.model_hash(m))
    assert preflight.check(docx, model=m) == []
    import docx as D
    doc = D.Document(io.BytesIO(docx))
    marks = {b.get(qn("w:name")) for b in doc.element.body.iter(qn("w:bookmarkStart"))}
    assert R.bookmark("CLAUSE_A~2.2") in marks
    sc_section = next(s for s in doc.sections
                      if "Special Conditions" in s.header.paragraphs[0].text)
    # a new page whose page numbers run on — never restarted; the schedules follow it
    assert sc_section._sectPr.find(qn("w:pgNumType")) is None
    assert sc_section.start_type == 2 and doc.sections[-1] is not sc_section
    parsed = [s.content for s in parse_docx(docx).segments]
    assert "Clause A.2 agreed text." in parsed
    # both parties' lines close the annexure, kept with its last entry
    assert any(t.startswith("| By | Party One Placeholder Limited") for t in parsed)


def test_a_named_clause_the_body_does_not_number_so_is_refused(placeholder, answers):
    template, clauses, cfg = _with_frame(placeholder)
    base = model_.resolve(template, clauses, answers)
    entries = _entries(base)
    entries[0]["target"] = {**entries[0]["target"], "number": "9.9"}
    with pytest.raises(model_.ModelError, match="does not number so"):
        model_.resolve(template, clauses, answers, special={
            "frame": clauses[("SC.FRAME", 1)], "config": cfg, "entries": entries})


@pytest.mark.skipif(not os.environ.get("LEGALMIND_SOFFICE"), reason=(
    "LEGALMIND_SOFFICE is not set: CI has no LibreOffice. Run it locally with "
    "LEGALMIND_SOFFICE=/root/legalmind-clm-local/lo/root/opt/libreoffice26.2/program/"
    "soffice"))
def test_the_pdf_starts_the_annexure_on_a_new_page_with_pages_running_on(
        placeholder, answers):
    import pymupdf

    from legalmind.drafting import pdf
    template, clauses, cfg = _with_frame(placeholder)
    base = model_.resolve(template, clauses, answers)
    m = model_.resolve(template, clauses, answers, special={
        "frame": clauses[("SC.FRAME", 1)], "config": cfg, "entries": _entries(base)})
    docx = R.render(m, template["assets"], contract_ref="T", version_number=2,
                    model_hash=model_.model_hash(m))
    fixed, result = pdf.convert_contract(docx)
    assert preflight.check(fixed, model=m, pdf=result.pdf) == []
    with pymupdf.open(stream=result.pdf, filetype="pdf") as doc:
        pages = [p.get_text() for p in doc]
    at = next(i for i, t in enumerate(pages) if "SPECIAL CONDITIONS" in t.upper()
              and "These Special Conditions form an integral part" in t)
    assert "Signatory Details" not in pages[at]           # its own page
    assert f"\n{at + 1}\n" in f"\n{pages[at]}" or str(at + 1) in pages[at]


# ---------------------------------------------------------------- derive (no DB)
def _unit(number, *texts, eid=None):
    return {"number": number, "texts": list(texts), "text": "\n".join(texts),
            "evidence_ids": [eid or str(uuid.uuid4())]}


def _row(kind, old, new, answer, **extra):
    return {"row_key": f"N|{kind}|{old['evidence_ids'][0] if old else ''}|"
                       f"{new['evidence_ids'][0] if new else ''}",
            "kind": kind, "effect_for_us": "NEGATIVE",
            "answer": {"answer": answer, **extra}}


def test_derive_maps_each_answer_to_one_entry_or_none(placeholder, answers):
    template, clauses = placeholder
    base = model_.resolve(template, clauses, answers)
    old = [_unit("4.1", "Clause C.1 text with Placeholder Term Two."),
           _unit("4.2", "Clause C.2 text."),
           _unit("5", "Clause D Heading", "Clause D conditional text, value Value D."),
           _unit("4.1", "Clause C.1 text with Placeholder Term Two.")]
    new = [_unit("4.1", "Clause C.1 text, changed."),
           _unit("4.2", "Clause C.2 text."), _unit("4.3", "Client inserted text."),
           _unit("5", "Clause D Heading", "Clause D changed.")]
    align = [(0, 0, False), (1, 1, False), (None, 2, False), (2, 3, False)]
    rows = [_row("MODIFIED", old[0], new[0], "accept_theirs"),
            _row("ADDED", None, new[2], "accept_theirs"),
            _row("MODIFIED", old[2], new[3], "write_wording", wording="Our clause D."),
            _row("MODIFIED", old[3], old[3], "keep_ours")]
    got = special_conditions.derive(rows, old, new, align, base, lambda _: None)
    assert got["blockers"] == []
    assert [(e["op"], e["target"]["number"], e.get("new_number"), e["text"])
            for e in got["entries"]] == [
        ("replace", "4.1", None, "Clause C.1 text, changed."),
        ("insert_after", "4.2", "4.2A", "Client inserted text."),
        ("replace", "5", None, "Our clause D.")]
    # a formatting-only acceptance (typography) gives no entry
    typo = _unit("4.1", "Clause C.1 text with Placeholder Term Two.")
    same = special_conditions.derive([_row("MODIFIED", old[0], typo, "accept_theirs")],
                                     old, [typo], [(0, 0, False)], base, lambda _: None)
    assert same == {"entries": [], "blockers": []}


def test_derive_fails_closed_on_what_an_annexure_cannot_say(placeholder, answers):
    template, clauses = placeholder
    base = model_.resolve(template, clauses, answers)
    nested = _unit("2.1", "Clause A.1 text with Placeholder Term One and count 3.")
    front = _unit(None, "Preamble placeholder text dated 1 January 2026.")
    moved = _unit("4.2", "Clause C.2 text.")
    listed = _unit("2.2", "Clause A.2 text, option Option 1.", "List item one placeholder.")
    changed = [_unit("2.1", "Other."), _unit(None, "Other preamble."),
               _unit("2.2", "Other A.2.", "List item one placeholder.")]
    rows = [_row("MODIFIED", nested, changed[0], "accept_theirs"),
            _row("MODIFIED", front, changed[1], "accept_theirs"),
            _row("MOVED", moved, moved, "accept_theirs"),
            _row("MODIFIED", listed, changed[2], "accept_theirs")]
    got = special_conditions.derive(rows, [nested, front, moved, listed],
                                    [*changed[:2], moved, changed[2]],
                                    [(0, 0, False), (1, 1, False), (2, 2, True),
                                     (3, 3, False)], base, lambda _: None)
    assert got["entries"] == []
    # a sub-clause with sub-clauses, front matter, a move, a clause holding a list
    assert [b["code"] for b in got["blockers"]] == ["CANNOT_EXPRESS"] * 4


# ---------------------------------------------------------------- DB: B1 readiness
@pytest.fixture
def lawyer(db, seeded):
    person = make_user(db)
    person.name = "Counsel"
    grant_role(db, person, P.ROLE_LEGAL_DECISION_AUTHORITY)
    grant_role(db, person, P.ROLE_USER)
    return person


def _imported(db, user, placeholder):
    T.import_rows(db, *placeholder, actor_id=user.id)
    return db.query(M.TemplateVersion).filter_by(
        template_key="PLACEHOLDER.STRUCTURAL").one()


def test_the_reference_frame_is_imported_draft_and_never_ready_until_approved(
        db, api, user, seeded, placeholder, lawyer):
    tv = _imported(db, user, placeholder)
    assert special_conditions.readiness(db, tv)["missing"][0]["code"] == "NOT_CONFIGURED"
    T.attach_special_conditions(db, tv, actor_id=user.id)
    rows = db.execute(select(M.ClauseVersion).where(
        M.ClauseVersion.clause_key.in_(["SC.FRAME", "SC.PRECEDENCE"]))).scalars().all()
    assert {r.status for r in rows} == {"DRAFT"}                       # rules 7/21
    assert {library.label(r) for r in rows} == {
        "For management approval — Reference text — not approved by Legal"}
    assert [m["code"] for m in special_conditions.readiness(db, tv)["missing"]] == [
        "FRAME_NOT_APPROVED", "PRECEDENCE_NOT_APPROVED"]
    sign_in(api, db, lawyer)
    shown = api.get(f"{V1}/templates/{tv.id}").json()["data"]
    assert shown["special_conditions"]["ready"] is False
    assert "SC.FRAME" in {c["clause_key"] for c in shown["clauses"]}   # approved like any
    for pin in library.pins(tv):
        assert api.post(f"{V1}/templates/{tv.id}/clauses/{pin['clause_key']}/approve"
                        ).status_code == 200
    db.refresh(tv)
    assert special_conditions.readiness(db, tv) == {"ready": True, "missing": []}


# ---------------------------------------------------------------- DB: B4–B6 end to end
@pytest.fixture
def sc_template(db, api, user, seeded, placeholder, lawyer, monkeypatch):
    monkeypatch.delenv("LEGALMIND_SOFFICE", raising=False)
    tv = _imported(db, user, placeholder)
    T.attach_special_conditions(db, tv, actor_id=user.id, initials=True)
    db.add(M.ConfigurationSnapshot(snapshot_hash=uuid.uuid4().hex, created_by=user.id,
                                   created_at=datetime.now(UTC) - timedelta(days=1)))
    db.flush()
    sign_in(api, db, lawyer)
    for pin in library.pins(tv):
        assert api.post(f"{V1}/templates/{tv.id}/clauses/{pin['clause_key']}/approve"
                        ).status_code == 200
    done = api.post(f"{V1}/templates/{tv.id}/publish")
    assert done.status_code == 200, done.text
    return db.get(M.TemplateVersion, uuid.UUID(done.json()["data"]["id"]))


def _paragraph(doc, text):
    return next(p for p in doc.element.body.iter(qn("w:p"))
                if "".join(t.text or "" for t in p.iter(qn("w:t"))) == text)


def _set(p, text):
    ts = list(p.iter(qn("w:t")))
    ts[0].text = text
    for t in ts[1:]:
        t.text = ""


def _client_copy(data: bytes) -> bytes:
    """The client's edits, made in Word: 4.1 reworded, a paragraph added after 4.2,
    clause 5's text changed — untracked."""
    import docx as D
    doc = D.Document(io.BytesIO(data))
    _set(_paragraph(doc, "Clause C.1 text with Placeholder Term Two."),
         "Clause C.1 text with Placeholder Term Two, as the client asks.")
    c2 = _paragraph(doc, "Clause C.2 text.")
    added = copy.deepcopy(c2)
    c2.addnext(added)
    _set(added, "Clause C.3 text the client added.")
    _set(_paragraph(doc, "Clause D conditional text, value Value D."),
         "Clause D conditional text, value Value E.")
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


def _ingest(db, tmp_path, contract, data, role):
    from legalmind.ingestion.service import ingest_document
    from legalmind.ingestion.storage import LocalFilesystemStorage
    from legalmind.ingestion.validation import DOCX_MIME
    v = ingest_document(db, LocalFilesystemStorage(tmp_path / "objects"),
                        contract_id=contract.id, uploaded_by=contract.owner_id, data=data,
                        filename="returned.docx", declared_mime=DOCX_MIME).document_version
    v.doc_metadata = {**(v.doc_metadata or {}), "version_role": role,
                      **({"source": "COUNTERPARTY"} if role == "CLIENT_MODIFIED" else {})}
    db.flush()
    return v


@pytest.fixture
def negotiated(db, api, sc_template, lawyer, tmp_path, monkeypatch):
    """v1 made from the template by the lawyer (who owns the deal), v2 the client's
    copy, every change answered: 2.2 and the addition accepted (no standard measures
    them: the holder's answer, `AM-281`), clause 5 our wording."""
    from legalmind.api.storage import get_storage
    from legalmind.ingestion.storage import LocalFilesystemStorage
    storage = LocalFilesystemStorage(tmp_path / "objects")
    api.app.dependency_overrides[get_storage] = lambda: storage
    draft = api.post(f"{V1}/drafts", json={
        "template_version_id": str(sc_template.id),
        "answers": dict(sc_template.layout["check_values"])}).json()["data"]
    made = api.post(f"{V1}/drafts/{draft['id']}/create", json={"expected_version": 0})
    assert made.status_code == 201, made.text
    contract = db.get(M.Contract, uuid.UUID(made.json()["data"]["contract_id"]))
    v1 = db.get(M.DocumentVersion, uuid.UUID(made.json()["data"]["document_version_id"]))
    v2 = _ingest(db, tmp_path, contract, _client_copy(storage.get(v1.storage_key)),
                 "CLIENT_MODIFIED")
    listed = api.get(f"{V1}/contracts/{contract.id}/changes").json()["data"]["changes"]
    by = {(c["kind"], c["clause"]["number"]): c for c in listed}
    assert set(by) == {("MODIFIED", "4.1"), ("ADDED", "4.3"), ("MODIFIED", "5")}, by
    from urllib.parse import quote
    for key, answer, extra in (
            (("MODIFIED", "4.1"), "accept_theirs", {"reason": "Agreed on the call"}),
            (("ADDED", "4.3"), "accept_theirs", {"reason": "Agreed on the call"}),
            (("MODIFIED", "5"), "write_wording",
             {"reason": "Our counter", "wording": "Clause D text as we agree it.",
              "internal_note": "Legal only"})):
        r = api.post(f"{V1}/contracts/{contract.id}/changes/"
                     f"{quote(by[key]['row_key'], safe='')}/answers",
                     json={"answer": answer, "expected_version": 0, **extra})
        assert r.status_code == 201, r.text
    yield contract, v1, v2, storage
    api.app.dependency_overrides.pop(get_storage, None)


def test_the_final_contract_is_the_body_unchanged_plus_its_special_conditions(
        db, api, negotiated, lawyer):
    contract, v1, v2, storage = negotiated
    dry = api.get(f"{V1}/contracts/{contract.id}/package").json()["data"]
    assert dry["available"] is True, dry["blockers"]
    assert [(e["op"], e["target"]["number"], e.get("new_number"), e["text"])
            for e in dry["entries"]] == [
        ("replace", "4.1", None,
         "Clause C.1 text with Placeholder Term Two, as the client asks."),
        ("insert_after", "4.2", "4.2A", "Clause C.3 text the client added."),
        ("replace", "5", None, "Clause D text as we agree it.")]
    assert dry["precedence"]["approved"] is True
    url = f"{V1}/contracts/{contract.id}/package"
    stale = api.post(url, json={"expected_entries_sha256": "0" * 64})
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "STALE_PREVIEW"
    made = api.post(url, json={"expected_entries_sha256": dry["entries_sha256"]})
    assert made.status_code == 201, made.text
    body = made.json()["data"]
    v3 = db.get(M.DocumentVersion, uuid.UUID(body["document_version"]["id"]))
    assert v3.version_number == 3 and v3.doc_metadata["package_of"] == str(v2.id)
    assert body["document_version"]["package"] == {"of_version_id": str(v2.id),
                                                   "special_conditions": 3}
    assert db.execute(select(M.AuditEvent).where(
        M.AuditEvent.action == "contract.package_prepared",
        M.AuditEvent.entity_id == contract.id)).scalar_one()
    # the body is v1's, row for row; the annexure follows it
    raw = [s.content for s in parse_docx(storage.get(v3.storage_key)).segments
           if (s.metadata or {}).get("part") is None]
    ours = [s.content for s in parse_docx(storage.get(v1.storage_key)).segments
            if (s.metadata or {}).get("part") is None]
    at = raw.index("Annexure A — Special Conditions")
    schedules = next(i for i, t in enumerate(ours) if t.startswith("Schedule A"))
    assert raw[:at] == ours[:at] and at == schedules        # body and signature block
    assert raw[-(len(ours) - at):] == ours[at:]              # the schedules after it
    # the engine reads the effective contract: the evidence rows are the file's own
    clauses, status, _ = effective.effective_clauses(db, v3.id)
    assert status == effective.APPLIED
    by = {c.section_number: c.content for c in clauses if c.section_number}
    assert by["4.1"] == "Clause C.1 text with Placeholder Term Two, as the client asks."
    assert by["4.2A"] == "Clause C.3 text the client added."
    five = [c.content for c in clauses]
    assert five[five.index("Clause D Heading") + 1] == "Clause D text as we agree it."
    assert not any(c.content.startswith(("These Special Conditions", "| By"))
                   for c in clauses)
    # the round is closed; nothing more to answer
    assert api.get(f"{V1}/contracts/{contract.id}/package").json()["data"][
        "blockers"][0]["code"] == "NOTHING_TO_ANSWER"
    # the trace: who and why, our internal note to a holder of the positions right
    trace = api.get(f"{V1}/document-versions/{v3.id}/special-conditions").json()["data"]
    assert [t["op"] for t in trace["trace"]] == ["replace", "insert_after", "replace"]
    assert all(t["decided_by"] == "Counsel" for t in trace["trace"])
    assert trace["trace"][2]["internal_note"] == "Legal only"
    assert all(t.get("holder_answer_audit_id") for t in trace["trace"])

    # the client signs it back unchanged: the same contract, no change, applied
    v4 = _ingest(db, Path(storage.root).parent, contract, storage.get(v3.storage_key),
                 "CLIENT_MODIFIED")
    listed = negotiation.changes(db, contract, v3, v4, legal_position=True)
    assert listed["changes"] == [] and "special_conditions_not_applied" not in listed


def test_a_tampered_special_condition_is_never_read_as_the_contract(
        db, api, negotiated, user):
    contract, _, _, _ = negotiated
    dry = api.get(f"{V1}/contracts/{contract.id}/package").json()["data"]
    v3 = db.get(M.DocumentVersion, uuid.UUID(api.post(
        f"{V1}/contracts/{contract.id}/package",
        json={"expected_entries_sha256": dry["entries_sha256"]}).json()["data"][
        "document_version"]["id"]))
    meta = copy.deepcopy(v3.doc_metadata)
    meta["special_conditions"]["trace"][0]["text_sha256"] = "0" * 64
    v3.doc_metadata = meta
    db.flush()
    _, status, reason = effective.effective_clauses(db, v3.id)
    assert status == effective.NOT_APPLIED and "differ from the record" in reason
    snapshot = db.execute(select(M.ConfigurationSnapshot)).scalars().first()
    review = M.Review(contract_id=contract.id, document_version_id=v3.id,
                      configuration_snapshot_id=snapshot.id,
                      status=E.ReviewStatus.DRAFT, created_by=user.id)
    db.add(review)
    db.flush()
    run_analysis(db, review)
    assert review.status is E.ReviewStatus.ANALYSIS_FAILED


def test_an_undecided_round_and_another_reader_are_refused(db, api, negotiated, seeded):
    contract, _, v2, _ = negotiated
    url = f"{V1}/contracts/{contract.id}/changes"
    first = next(c for c in api.get(url).json()["data"]["changes"]
                 if c["clause"]["number"] == "4.1")
    from urllib.parse import quote
    # a change answered again with nothing: a new unanswered round is not possible, so
    # reopen by answering "keep ours" — the entry goes, the package lists two
    r = api.post(f"{url}/{quote(first['row_key'], safe='')}/answers",
                 json={"answer": "keep_ours", "expected_version": 1})
    assert r.status_code == 201, r.text
    dry = api.get(f"{V1}/contracts/{contract.id}/package").json()["data"]
    assert len(dry["entries"]) == 2
    other = make_user(db)
    grant_role(db, other, P.ROLE_USER)
    sign_in(api, db, other)
    assert api.get(f"{V1}/contracts/{contract.id}/package").status_code == 404
    assert api.post(f"{V1}/contracts/{contract.id}/package",
                    json={"expected_entries_sha256": dry["entries_sha256"]}
                    ).status_code == 404


def test_an_entry_worse_for_us_needs_the_decision_that_accepted_it():
    """R-12: the annexure is never a way round the evaluator. A rejection, or another
    wording's approval, never lets an entry stand (L-1)."""
    from types import SimpleNamespace as NS

    from legalmind.api.routers.negotiation import _lets_stand, _trace_blockers
    reject = NS(decision_type=E.DecisionType.REJECT)
    assert _lets_stand(None, None, reject, "x" * 64) is False
    assert _lets_stand(None, None, NS(decision_type=E.DecisionType.ACCEPT_DEVIATION),
                       None) is True
    assert _lets_stand(None, None, NS(decision_type=E.DecisionType.APPROVE_CUSTOMIZATION),
                       None) is False                       # no wording: nothing approved
    trace = [{"n": 1, "row_key": "k", "choice_id": "c", "effect": "NEGATIVE",
              "decision_ids": []}]
    assert [b["code"] for b in _trace_blockers(trace, [{"answer": "accept_theirs"}])] \
        == ["SC_TRACE"]
    assert _trace_blockers(trace, [{"answer": "use_standard"}]) == []
    assert _trace_blockers([{**trace[0], "decision_ids": ["d"]}],
                           [{"answer": "accept_theirs"}]) == []


def test_decisions_and_the_gate_follow_a_package_as_they_follow_a_reply(
        api, db, seeded, tmp_path):
    """B6: `carry_decisions` and `reply_open_points` key on ``package_of`` as on
    ``reply_to`` — the version our answer was prepared for (`AM-307` r8 / AM-284 r2)."""
    from legalmind.analysis.negotiation import reply_open_points
    from legalmind.workflow.decisions import carry_decisions
    from tests.test_negotiation import owner as _owner_fixture  # noqa: F401
    from tests.test_negotiation_carry import _point, _prepared, _theirs_rv
    from tests.test_negotiation_wording import _lawyer, _measured
    person = make_user(db)
    grant_role(db, person, P.ROLE_USER)
    sign_in(api, db, person)
    db.add(M.ConfigurationSnapshot(snapshot_hash=uuid.uuid4().hex, created_by=person.id,
                                   created_at=datetime.now(UTC) - timedelta(days=1)))
    c, _, review = _measured(db, tmp_path, person)
    lawyer = _lawyer(db)
    change = api.get(f"{V1}/contracts/{c.id}/changes").json()["data"]["changes"][0]
    ev_id = uuid.UUID(change["review"]["after"][0]["evaluation_ids"][0])
    db.add(M.LegalDecision(finding_id=db.get(M.Evaluation, ev_id).finding_id,
                           evaluation_id=ev_id, decision_type=E.DecisionType.ACCEPT_DEVIATION,
                           justification="accepted", decided_by=lawyer.id, version_number=1))
    db.flush()
    from urllib.parse import quote
    assert api.post(f"{V1}/contracts/{c.id}/changes/{quote(change['row_key'], safe='')}"
                    "/answers", json={"answer": "accept_theirs", "expected_version": 0}
                    ).status_code == 201
    ours, ours_review = _prepared(api, db, c)
    meta = dict(ours.doc_metadata)
    meta["package_of"] = meta.pop("reply_to")
    ours.doc_metadata = meta
    db.flush()
    _point(db, ours_review, _theirs_rv(db, review), ours)
    assert reply_open_points(db, ours) is not None            # gated as a reply is
    assert carry_decisions(db, ours_review) == 1
    assert reply_open_points(db, ours) is None


def test_a_run_in_title_keeps_its_mark_and_names_the_entry(placeholder, answers):
    """A sub-clause's own run-in title is its heading in the lead, and stays underlined
    where the agreed text opens on it; a parent clause's heading is never borrowed."""
    template, clauses, cfg = _with_frame(placeholder)
    clauses[("CLAUSE_C", 1)]["body"][1]["title"] = "Second Point:"
    base = model_.resolve(template, clauses, answers)
    t = special_conditions.targets(base)
    assert t["4.2"]["heading"] == "Second Point" and t["4.1"]["heading"] is None
    m = model_.resolve(template, clauses, answers, special={
        "frame": clauses[("SC.FRAME", 1)], "config": cfg, "entries": [
            {"n": 1, "op": "replace", "target": special_conditions._public(t["4.2"]),
             "text": "Second Point: agreed words."}]})
    entry = m["special_conditions"]["entries"][0]
    assert model_.text_of(entry["lead"]) == \
        "Clause 4.2 “Second Point” is replaced by the following:"
    assert entry["blocks"][0] == [{"t": "Second Point", "u": True},
                                  {"t": ": agreed words."}]


def test_the_precedence_sentence_goes_into_the_order_of_precedence_sub_clause(
        db, user, seeded, placeholder):
    template, clauses = copy.deepcopy(placeholder)
    body = clauses[("CLAUSE_C", 1)]["body"]
    body[1] = {**body[1], "title": "Order of Precedence:"}
    clauses[("CLAUSE_C", 1)] = T.check_clause({**clauses[("CLAUSE_C", 1)],
                                               "content_hash": None})
    template["content_hash"] = library.template_hash(template, clauses)
    tv = _imported(db, user, (template, clauses))
    T.attach_special_conditions(db, tv, actor_id=user.id, precedence_into="CLAUSE_C")
    pin = next(p for p in tv.clauses if p["clause_key"] == "CLAUSE_C")
    row = db.execute(select(M.ClauseVersion).where(
        M.ClauseVersion.clause_key == "CLAUSE_C",
        M.ClauseVersion.version == pin["version"])).scalar_one()
    assert pin["version"] == 2 and row.status == "DRAFT"
    assert row.body[1]["text"].startswith("Clause C.2 text. The Special Conditions")
    assert "SC.PRECEDENCE" not in {p["clause_key"] for p in tv.clauses}   # no 2nd clause
    assert special_conditions.config(tv)["precedence"] == "CLAUSE_C"


# ---------------------------------------------------------------- review fixes (doc 12)
def _package(db, api, contract):
    dry = api.get(f"{V1}/contracts/{contract.id}/package").json()["data"]
    made = api.post(f"{V1}/contracts/{contract.id}/package",
                    json={"expected_entries_sha256": dry["entries_sha256"]})
    assert made.status_code == 201, made.text
    return db.get(M.DocumentVersion, uuid.UUID(made.json()["data"]["document_version"]["id"]))


def _without(data: bytes, text: str) -> bytes:
    import docx as D
    doc = D.Document(io.BytesIO(data))
    p = _paragraph(doc, text)
    p.getparent().remove(p)
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


def test_a_renumbered_body_is_never_read_as_another_clause(db, api, negotiated, user):
    """H-1: the client returns the final contract with 4.1 deleted — Word renumbers 4.2
    to 4.1. The entries name 4.1 and 4.2 by number; neither is the clause the body now
    holds there. NOT_APPLIED (a person decides), never a KeyError or the wrong clause."""
    contract, _, _, storage = negotiated
    v3 = _package(db, api, contract)
    v4 = _ingest(db, Path(storage.root).parent, contract,
                 _without(storage.get(v3.storage_key),
                          "Clause C.1 text with Placeholder Term Two."), "CLIENT_MODIFIED")
    clauses, status, reason = effective.effective_clauses(db, v4.id)
    assert status == effective.NOT_APPLIED and "renumbered" in reason
    listed = negotiation.changes(db, contract, v3, v4, legal_position=True)
    assert listed["special_conditions_not_applied"]
    assert {c["route"] for c in listed["changes"]} == {"holder"}


def test_a_later_copy_without_the_annexure_is_read_raw_for_a_person(
        db, api, negotiated, user):
    """M-2: once a package exists, the client's own paper (here, our v1 again) holds no
    annexure. It reads raw, says so, and its analysis runs — never ANALYSIS_FAILED."""
    contract, v1, _, storage = negotiated
    v3 = _package(db, api, contract)
    v4 = _ingest(db, Path(storage.root).parent, contract, storage.get(v1.storage_key),
                 "CLIENT_MODIFIED")
    raw, status, reason = effective.effective_clauses(db, v4.id)
    assert status == effective.ABSENT and reason == effective.ABSENT_REASON
    assert raw == effective.load_clauses(db, v4.id)
    listed = negotiation.changes(db, contract, v3, v4, legal_position=True)
    assert listed["special_conditions_not_applied"] == [effective.ABSENT_REASON]
    snapshot = db.execute(select(M.ConfigurationSnapshot)).scalars().first()
    review = M.Review(contract_id=contract.id, document_version_id=v4.id,
                      configuration_snapshot_id=snapshot.id,
                      status=E.ReviewStatus.DRAFT, created_by=user.id)
    db.add(review)
    db.flush()
    run_analysis(db, review)
    assert review.status is not E.ReviewStatus.ANALYSIS_FAILED


def test_two_insertions_after_one_clause_keep_their_order():
    """M-1: 17.2A then 17.2B, both after 17.2, read in that order."""
    from legalmind.mapping.engine import Clause
    row = lambda n, t: Clause(evidence_id=uuid.uuid4(), content=t,  # noqa: E731
                              section_number=n)
    body = [row("4.1", "Four one."), row("4.2", "Four two."), row("5", "Five")]
    entries = [{"op": "insert_after", "number": "4.2", "new": "4.2A", "heading": None,
                "rows": [row(None, "A text.")]},
               {"op": "insert_after", "number": "4.2", "new": "4.2B", "heading": None,
                "rows": [row(None, "B text.")]}]
    targets = {"4.2": {"lead": "Four two."}}
    out = effective._rewrite(body, entries, set(), targets)
    assert [c.section_number for c in out] == ["4.1", "4.2", "4.2A", "4.2B", "5"]


def test_every_answer_takes_the_contract_lock_a_package_takes(db, api, negotiated):
    """M-3: answering waits on the same contract row lock as preparing the package, so
    no answer lands between the package's read and its write."""
    from sqlalchemy import event
    contract, _, _, _ = negotiated
    change = next(c for c in api.get(f"{V1}/contracts/{contract.id}/changes").json()[
        "data"]["changes"] if c["clause"]["number"] == "4.3")
    seen: list[str] = []

    def capture(conn, cursor, statement, *args):
        seen.append(statement)
    event.listen(db.get_bind(), "before_cursor_execute", capture)
    try:
        from urllib.parse import quote
        r = api.post(f"{V1}/contracts/{contract.id}/changes/"
                     f"{quote(change['row_key'], safe='')}/answers",
                     json={"answer": "keep_ours", "expected_version": 1})
        assert r.status_code == 201, r.text
    finally:
        event.remove(db.get_bind(), "before_cursor_execute", capture)
    lock = next(i for i, q in enumerate(seen)
                if "FROM contracts" in q and "FOR UPDATE" in q)
    write = next(i for i, q in enumerate(seen) if q.startswith("INSERT INTO comparison"))
    assert lock < write


def test_a_holder_answer_counts_only_while_it_is_the_current_answer(
        db, api, negotiated, lawyer):
    """L-2: the addition's audited holder answer (version 1) is replaced by a second
    answer that no audit row records; the old audit row no longer lets the entry stand."""
    from legalmind.analysis import document_comparison
    contract, v1, v2, _ = negotiated
    change = next(c for c in api.get(f"{V1}/contracts/{contract.id}/changes").json()[
        "data"]["changes"] if c["clause"]["number"] == "4.3")
    document_comparison.write_choices(
        db, (v1.id, None), (v2.id, None), {change["row_key"]: "theirs"}, lawyer.id,
        reason="written elsewhere", expected={change["row_key"]: 1})
    dry = api.get(f"{V1}/contracts/{contract.id}/package").json()["data"]
    made = api.post(f"{V1}/contracts/{contract.id}/package",
                    json={"expected_entries_sha256": dry["entries_sha256"]})
    assert made.status_code == 409, made.text
    assert [b["code"] for b in made.json()["error"]["blockers"]] == ["SC_TRACE"]


def test_carried_rows_are_order_free_only_for_a_final_contract():
    """L-3: a tracked reply keeps the document's order; only a final contract, whose
    annexure holds a varied clause after the body, reads its rows in any order."""
    from legalmind.workflow.decisions import _hash_rows
    assert _hash_rows(["a", "b"]) != _hash_rows(["b", "a"])
    assert _hash_rows(["a", "b"], True) == _hash_rows(["b", "a"], True)


def test_a_varied_clauses_heading_is_exempt_only_inside_the_annexure(placeholder, answers):
    """L-4: the same quoted heading in the body is still an undefined term."""
    template, clauses, cfg = _with_frame(placeholder)
    clauses[("CLAUSE_E", 1)]["body"].append(
        {"kind": "p", "text": "See “Clause C Heading” for the rest."})
    base = model_.resolve(template, clauses, answers)
    m = model_.resolve(template, clauses, answers, special={
        "frame": clauses[("SC.FRAME", 1)], "config": cfg, "entries": _entries(base)})
    docx = R.render(m, template["assets"], contract_ref="T", version_number=2,
                    model_hash=model_.model_hash(m))
    assert [p.detail for p in preflight.check(docx, model=m)] == [
        "“Clause C Heading” is used in quotes and never defined"]


def test_the_preview_hash_covers_the_frame_and_the_answers():
    """L-5: a re-approved frame, or an answer behind an entry, changes the hash."""
    entries = [{"n": 1, "op": "replace", "target": {"key": "K"}, "text": "t",
                "answer": "accept_theirs", "effect": "NEGATIVE"}]
    h = special_conditions.entries_sha256
    assert h(entries, ["SC.FRAME@1"]) != h(entries, ["SC.FRAME@2"])
    assert h(entries, ["SC.FRAME@1"]) != h([{**entries[0], "answer": "write_wording"}],
                                           ["SC.FRAME@1"])
