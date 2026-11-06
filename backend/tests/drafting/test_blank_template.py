"""`AM-302` (AB-159, owner 2026-11-04) — the blank template, filled outside LegalMind,
and the safety net when it comes back: published only, audited, every field a visible
placeholder, the template ID in the footer; a returned copy linked by that ID (or by its
structure) and every edit beyond the filled fields listed as a change; an older version
said so. The DRAFT's review copy for management. The STRUCTURAL placeholder template and
synthetic text only (rule 21)."""

from __future__ import annotations

import io
import uuid
import zipfile

import docx
import pytest
from sqlalchemy import select

from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.drafting import blank, library, pdf
from legalmind.drafting import model as model_
from legalmind.ingestion.service import ingest_document
from legalmind.ingestion.storage import LocalFilesystemStorage
from legalmind.security import audit as A
from legalmind.security import permissions as P
from tests.conftest import grant_role, make_user, sign_in
from tests.drafting.test_new_contract import published, staff  # noqa: F401 — fixtures
from tools import import_template as T

V1 = "/api/v1"
KEY = "PLACEHOLDER.STRUCTURAL"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
FILLED = {"[Effective date]": "1 January 2027", "[Client's legal name]": "Synthetic Client",
          "[Client's registered office]": "1 Synthetic Road", "[Our CIN]": "",
          "[Client's CIN or LLPIN]": "", "[Placeholder count]": "3",
          "[Placeholder option]": "Option 1", "[Placeholder clause D text]": "Dee"}


# ---------------------------------------------------------------- the model and file
def test_the_blank_shows_every_field_as_a_placeholder_and_keeps_optional_parts(placeholder):
    template, clauses = placeholder
    m = model_.resolve(template, clauses, {}, blank=True)
    shown = blank.placeholders(m)
    assert {"[Effective date]", "[Client's legal name]", "[Client signatory's name]",
            "[Our signatory's designation]"} <= shown
    # a field our standard fixes is filled, never a placeholder
    assert "Party One Placeholder Limited" in model_.text_of(m["parties"][0]["name"])
    d = next(c for c in m["body"] if c["clause_key"] == "CLAUSE_D")
    assert d["note"] == ("[Optional: include this only if “Include placeholder clause D?” "
                         "is Yes; otherwise delete it.]")
    assert any(s.get("note") for s in m["schedules"])
    # the filled contract's model is unchanged: no placeholder, no note
    filled = model_.resolve(template, clauses, template["layout"]["check_values"])
    assert not blank.placeholders(filled) and "note" not in str(filled["body"])


def test_the_blank_file_highlights_placeholders_without_content_controls(placeholder):
    template, clauses = placeholder
    m = model_.resolve(template, clauses, {}, blank=True)
    from legalmind.drafting import render_contract
    data = render_contract.render(m, template["assets"], contract_ref=f"TPL-{KEY}",
                                  version_number=1, model_hash=model_.model_hash(m),
                                  blank=True, header_note="DEMO — not approved by Legal")
    xml = zipfile.ZipFile(io.BytesIO(data)).read("word/document.xml").decode()
    assert "<w:sdt>" not in xml and "w:sdt " not in xml
    assert 'w:highlight w:val="yellow"' in xml
    d = docx.Document(io.BytesIO(data))
    footer = d.sections[0].footer.paragraphs[0].text
    assert blank.ID.search(footer)["key"] == KEY
    assert footer.startswith(f"LM-TPL-{KEY}-v1-{model_.model_hash(m)[:8]}")
    assert all("DEMO — not approved by Legal" in s.header.paragraphs[0].text
               for s in d.sections)


# ---------------------------------------------------------------- the download
def test_only_a_published_template_downloads_and_every_download_is_audited(
        db, api, published, staff):
    sign_in(api, db, staff)
    got = api.get(f"{V1}/templates/{KEY}/blank", params={"format": "docx"})
    assert got.status_code == 200, got.text
    assert got.headers["content-type"] == DOCX
    assert "blank template v1.docx" in got.headers["content-disposition"]
    footer = docx.Document(io.BytesIO(got.content)).sections[0].footer.paragraphs[0].text
    assert footer.startswith(f"LM-TPL-{KEY}-v1-")
    [event] = db.execute(select(M.AuditEvent).where(
        M.AuditEvent.action == A.TEMPLATE_BLANK_DOWNLOADED)).scalars()
    assert event.actor_id == staff.id and event.entity_id == published.id
    assert event.after_state["format"] == "docx" and event.after_state["version"] == 1
    assert event.after_state["template_id"] == footer.split()[0]
    # unknown key, a format we do not make
    assert api.get(f"{V1}/templates/NOPE/blank").status_code == 404
    assert api.get(f"{V1}/templates/{KEY}/blank", params={"format": "rtf"}
                   ).status_code == 422


def test_a_draft_is_404_and_a_retired_version_409(db, api, user, seeded, placeholder, staff):
    T.import_rows(db, *placeholder, actor_id=user.id)
    sign_in(api, db, staff)
    draft = api.get(f"{V1}/templates/{KEY}/blank")
    unknown = api.get(f"{V1}/templates/NO.SUCH.KEY/blank")
    assert draft.status_code == unknown.status_code == 404
    assert {k: v for k, v in draft.json()["error"].items() if k != "request_id"} == \
        {k: v for k, v in unknown.json()["error"].items() if k != "request_id"}
    assert api.get(f"{V1}/templates/{KEY}/blank", params={"version": 1}).status_code == 404
    tv = db.execute(select(M.TemplateVersion)).scalar_one()
    tv.status = "RETIRED"
    db.flush()
    retired = api.get(f"{V1}/templates/{KEY}/blank", params={"version": 1})
    assert retired.status_code == 409


def test_no_contract_create_permission_is_refused(db, api, published):
    nobody = make_user(db)
    sign_in(api, db, nobody)
    assert api.get(f"{V1}/templates/{KEY}/blank").status_code in (403, 404)


def test_the_pdf_is_made_by_the_worker_path(db, api, published, staff, monkeypatch):
    sign_in(api, db, staff)
    url = f"{V1}/templates/{KEY}/blank"
    # no LibreOffice on this host: recorded FAILED, said plainly, Word offered
    failed = api.get(url, params={"format": "pdf"})
    assert failed.status_code == 503 and failed.json()["error"]["code"] == "PDF_NOT_MADE"
    assert "Word file" in failed.json()["error"]["message"]
    digest = model_.model_hash(blank.blank_model(db, published))
    # a render in flight is 202
    pdf.mark_blank(db, published.id, digest, blank.BLANK, pdf.RENDERING)
    waiting = api.get(url, params={"format": "pdf"})
    assert waiting.status_code == 202 and waiting.headers["Retry-After"] == "3"
    # once made, served as stored and audited
    monkeypatch.setattr(pdf, "convert", lambda data: pdf.PdfResult(b"%PDF-1.7 x", "LO"))
    monkeypatch.setattr(pdf, "STALE_S", -1)
    made = api.get(url, params={"format": "pdf"})
    assert made.status_code == 200 and made.content == b"%PDF-1.7 x"
    assert pdf.blank_record(db, published.id, digest)["status"] == pdf.READY
    assert db.execute(select(M.AuditEvent).where(
        M.AuditEvent.action == A.TEMPLATE_BLANK_DOWNLOADED)).scalars().one(
    ).after_state["format"] == "pdf"


# ---------------------------------------------------------------- the review copy
def test_the_review_copy_is_a_drafts_and_only_legal_or_the_lead_get_it(
        db, api, user, seeded, placeholder, staff):
    T.import_rows(db, *placeholder, actor_id=user.id)
    tv = db.execute(select(M.TemplateVersion)).scalar_one()
    url = f"{V1}/templates/{tv.id}/review-copy"
    sign_in(api, db, staff)
    hidden, absent = api.get(url), api.get(f"{V1}/templates/{uuid.uuid4()}/review-copy")
    assert hidden.status_code == absent.status_code == 404
    for role in (P.ROLE_LEGAL_DECISION_AUTHORITY, P.ROLE_DEPARTMENT_LEAD):
        person = make_user(db)
        grant_role(db, person, role)
        sign_in(api, db, person)
        got = api.get(url)
        assert got.status_code == 200, (role, got.text)
        d = docx.Document(io.BytesIO(got.content))
        assert blank.REVIEW_HEADER in d.sections[0].header.paragraphs[0].text
        footer = d.sections[0].footer.paragraphs[0].text
        assert footer.startswith(f"LM-REVIEW-{KEY}-v1-") and not blank.ID.search(footer)
    events = db.execute(select(M.AuditEvent).where(
        M.AuditEvent.action == A.TEMPLATE_BLANK_DOWNLOADED)).scalars().all()
    assert [e.after_state["kind"] for e in events] == ["review", "review"]


def test_a_published_template_has_no_review_copy(db, api, published):
    lawyer = make_user(db)
    grant_role(db, lawyer, P.ROLE_LEGAL_DECISION_AUTHORITY)
    sign_in(api, db, lawyer)
    assert api.get(f"{V1}/templates/{published.id}/review-copy").status_code == 409


def test_publish_records_the_approval_reference(db, api, user, seeded, placeholder,
                                                monkeypatch):
    monkeypatch.delenv("LEGALMIND_SOFFICE", raising=False)
    T.import_rows(db, *placeholder, actor_id=user.id)
    tv = db.execute(select(M.TemplateVersion)).scalar_one()
    db.add(M.ConfigurationSnapshot(snapshot_hash=uuid.uuid4().hex, created_by=user.id))
    lawyer = make_user(db)
    grant_role(db, lawyer, P.ROLE_LEGAL_DECISION_AUTHORITY)
    db.flush()
    sign_in(api, db, lawyer)
    for pin in library.pins(tv):
        api.post(f"{V1}/templates/{tv.id}/clauses/{pin['clause_key']}/approve")
    done = api.post(f"{V1}/templates/{tv.id}/publish",
                    json={"approval_reference": "  Management approval, email of 5 Nov "
                          "2026 "})
    assert done.status_code == 200, done.text
    event = db.execute(select(M.AuditEvent).where(
        M.AuditEvent.action == "template.published")).scalar_one()
    assert event.after_state["approval_reference"] == \
        "Management approval, email of 5 Nov 2026"
    assert api.get(f"{V1}/templates/{tv.id}").json()["data"]["approval_reference"] == \
        "Management approval, email of 5 Nov 2026"


# ---------------------------------------------------------------- when it comes back
def _fill(data: bytes, *, edit: tuple[str, str] | None = None,
          footer: bool = True) -> bytes:
    """The blank as a salesperson returns it: every placeholder filled, every note
    deleted, optionally one sentence changed and the footer ID lost."""
    d = docx.Document(io.BytesIO(data))
    paragraphs = list(d.paragraphs) + [p for t in d.tables for r in t.rows
                                       for c in r.cells for p in c.paragraphs]
    for p in paragraphs:
        if p.text.startswith(model_.NOTE_OPEN):
            p._p.getparent().remove(p._p)
            continue
        for run in p.runs:
            if run.text in FILLED:
                run.text = FILLED[run.text]
            elif edit and run.text == edit[0]:
                run.text = edit[1]
    if not footer:
        for s in d.sections:
            for p in [*s.footer.paragraphs, *s.first_page_footer.paragraphs]:
                for run in p.runs:
                    run.text = ""
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def _returned(db, tmp_path, owner, data, contract_type="OTHER"):
    contract = M.Contract(owner_id=owner.id, name="Returned blank",
                          contract_type=contract_type, status=E.ContractStatus.ACTIVE)
    db.add(contract)
    db.flush()
    ingest_document(db, LocalFilesystemStorage(tmp_path / "objects"),
                    contract_id=contract.id, uploaded_by=owner.id, data=data,
                    filename="returned.docx", declared_mime=DOCX)
    return contract


def _blank_bytes(api):
    got = api.get(f"{V1}/templates/{KEY}/blank")
    assert got.status_code == 200
    return got.content


@pytest.mark.parametrize("footer", [True, False], ids=["by-id", "by-structure"])
def test_a_filled_copy_is_linked_and_only_real_edits_are_changes(
        db, api, published, staff, tmp_path, footer):
    sign_in(api, db, staff)
    filled = _fill(_blank_bytes(api), footer=footer)
    contract = _returned(db, tmp_path, staff, filled)
    listed = api.get(f"{V1}/contracts/{contract.id}/changes")
    assert listed.status_code == 200, listed.text
    body = listed.json()["data"]
    assert body["template"]["template_key"] == KEY and body["template"]["version"] == 1
    assert body["template"]["how"] == ("id" if footer else "structure")
    assert body["template"]["older"] is False
    assert [(c["before"], c["after"]) for c in body["changes"]] == []  # filling is no change

    edited = _fill(_blank_bytes(api), edit=("Clause C.2 text.",
                                            "Clause C.2 text, unless the client agrees."))
    contract = _returned(db, tmp_path, staff, edited)
    rows = api.get(f"{V1}/contracts/{contract.id}/changes").json()["data"]["changes"]
    assert [(c["kind"], c["clause"]["number"]) for c in rows] == [("MODIFIED", "4.2")]
    assert rows[0]["effect_for_us"] in ("POSITIVE", "NEUTRAL", "NEGATIVE")
    assert "Clause C.2 text." in rows[0]["before"]["text"]


def test_an_optional_part_deleted_as_its_note_says_is_not_a_change(
        db, api, published, staff, tmp_path):
    sign_in(api, db, staff)
    d = docx.Document(io.BytesIO(_fill(_blank_bytes(api))))
    for p in list(d.paragraphs):
        if p.text.startswith(("Clause D", "Schedule B")):
            p._p.getparent().remove(p._p)
    buf = io.BytesIO()
    d.save(buf)
    contract = _returned(db, tmp_path, staff, buf.getvalue())
    rows = api.get(f"{V1}/contracts/{contract.id}/changes").json()["data"]["changes"]
    assert rows == []


def test_a_copy_of_an_older_version_says_so(db, api, published, staff, tmp_path, user):
    sign_in(api, db, staff)
    old = _fill(_blank_bytes(api))
    # v2 published, v1 retired (as the publish path leaves them)
    v2 = M.TemplateVersion(**{c: getattr(published, c) for c in (
        "template_key", "doc_type", "brand", "layout", "clauses", "variables",
        "annexures", "assets", "source", "content_hash", "created_by")}, version=2)
    db.add(v2)
    db.flush()
    published.status = "RETIRED"
    db.flush()
    v2.status, v2.approved_by = "APPROVED", user.id
    db.flush()
    v2.status, v2.published_by = "PUBLISHED", user.id
    v2.checked_snapshot_id = published.checked_snapshot_id
    db.flush()
    contract = _returned(db, tmp_path, staff, old)
    said = api.get(f"{V1}/contracts/{contract.id}/changes").json()["data"]["template"]
    assert said["version"] == 1 and said["current_version"] == 2 and said["older"]
    assert said["message"] == "Made from an older template (v1); the current one is v2."
    # the retired version itself no longer downloads by default; v2 does
    assert api.get(f"{V1}/templates/{KEY}/blank", params={"version": 1}
                   ).status_code == 409
    assert "-v2-" in docx.Document(io.BytesIO(_blank_bytes(api))
                                   ).sections[0].footer.paragraphs[0].text


def test_keeping_ours_on_a_returned_blank_writes_the_template_text_back(
        db, api, published, staff, tmp_path, monkeypatch):
    monkeypatch.delenv("LEGALMIND_SOFFICE", raising=False)
    sign_in(api, db, staff)
    edited = _fill(_blank_bytes(api), edit=("Clause C.2 text.", "Clause C.2 text, changed."))
    contract = _returned(db, tmp_path, staff, edited)
    [change] = api.get(f"{V1}/contracts/{contract.id}/changes").json()["data"]["changes"]
    answered = api.post(f"{V1}/contracts/{contract.id}/changes/"
                        f"{change['row_key'].replace('|', '%7C')}/answers",
                        json={"answer": "keep_ours", "expected_version": 0})
    assert answered.status_code == 201, answered.text
    reply = api.post(f"{V1}/contracts/{contract.id}/reply")
    assert reply.status_code == 201, reply.text
    assert reply.json()["data"]["kept_ours"] == 1
    from legalmind.ingestion.parsing import parse_docx
    got = api.get(f"{V1}{reply.json()['data']['downloads']['docx']}").content
    texts = [s.content for s in parse_docx(got).segments]
    assert "Clause C.2 text." in texts and "Clause C.2 text, changed." not in texts


def test_the_contract_says_its_only_version_was_made_from_the_template(
        db, api, published, staff, tmp_path):
    sign_in(api, db, staff)
    contract = _returned(db, tmp_path, staff, _fill(_blank_bytes(api)))
    [version] = api.get(f"{V1}/contracts/{contract.id}").json()["data"]["document_versions"]
    assert version["made_from_template"]["template_key"] == KEY
