"""The deal cycle ends at the final clean copy — `AM-318` (owner, 2026-11-06).

Stamping and signing happen in another tool. A deal is Final once its latest version is
our final contract (an Annexure package, or a final copy) and Legal recorded Sign as is
on it. Every document here is synthetic; none names a client.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest import mock

import pytest
from sqlalchemy import select

from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.domain.deal_stage import NegotiationStage as S
from legalmind.domain.deal_stage import ReviewFacts, VersionFacts, derive_stage
from legalmind.drafting import clean
from legalmind.workflow import contract_outcome as CO
from legalmind.workflow.errors import InvalidTransition
from tests.test_negotiation import (  # noqa: F401 — `owner` is a fixture
    _changes,
    _contract,
    _docx,
    _ingest,
    _review,
    owner,
)
from tests.test_negotiation_reply import (
    OURS,
    THEIRS,
    _answer,
    _negotiated,
    _text,
    published,  # noqa: F401 — autouse fixture
)
from tests.test_version_comparison import V1

T0 = datetime(2026, 11, 1, tzinfo=UTC)
FINAL = f"{V1}/contracts/{{}}/final-copy"


def _at(d: int) -> datetime:
    return T0 + timedelta(days=d)


# ------------------------------------------------------------------ the pure stage
def test_a_final_contract_signed_as_is_is_final_even_once_recorded_as_sent():
    final = VersionFacts(3, _at(3), "COMPANY_DRAFT", _at(5), True, True)
    review = ReviewFacts(outcome="SIGN_AS_IS", outcome_at=_at(4))
    assert derive_stage(_at(0), [final], review) == (S.FINAL, _at(4))


def test_a_final_contract_awaiting_the_decision_is_with_legal():
    final = VersionFacts(3, _at(3), "COMPANY_DRAFT", None, True, True)
    assert derive_stage(_at(0), [final], ReviewFacts(reply_cleared=True)) == (
        S.INTERNAL_REVIEW, _at(3))


def test_sign_as_is_on_a_version_that_is_not_final_is_ready_for_the_final_contract():
    draft = VersionFacts(1, _at(1), "COMPANY_DRAFT")
    review = ReviewFacts(outcome="SIGN_AS_IS", outcome_at=_at(2))
    assert derive_stage(_at(0), [draft], review)[0] is S.READY_TO_SIGN


def test_a_legacy_signed_deal_stays_signed():
    signed = VersionFacts(4, _at(4), "FINAL_SIGNED")
    assert derive_stage(_at(0), [signed])[0] is S.SIGNED


# ------------------------------------------------------------------ the final copy
def test_the_client_accepted_our_draft_unchanged(api, db, owner, tmp_path):
    """B4: nothing to answer — the final copy is our version, clean."""
    c = _contract(db, owner)
    ours = _ingest(db, tmp_path, c, _docx(*OURS), "ours.docx")
    _review(db, ours, [])                          # analysed, nothing undecided
    dry = api.get(FINAL.format(c.id)).json()["data"]
    assert (dry["available"], dry["mode"], dry["agreed"]) == (True, "copy", [])
    r = api.post(FINAL.format(c.id))
    assert r.status_code == 201, r.text
    v = db.get(M.DocumentVersion, uuid.UUID(r.json()["data"]["document_version"]["id"]))
    assert v.version_number == 2 and v.doc_metadata["final_copy_of"] == str(ours.id)
    assert v.doc_metadata["version_role"] == "COMPANY_DRAFT"
    # a final copy is never a second final copy
    again = api.post(FINAL.format(c.id))
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "FINAL_COPY_NOT_READY"


def test_an_undecided_legal_point_blocks_the_final_copy(api, db, owner, tmp_path):
    """Fail closed (integration 2026-11-12): the dry run lists the undecided point and
    the POST refuses — never a final contract made while Legal still has to decide."""
    c = _contract(db, owner)
    ours = _ingest(db, tmp_path, c, _docx(*OURS), "ours.docx")
    _review(db, ours, [(0, E.FindingClassification.DEVIATION, E.RuleOutcome.UNACCEPTABLE)])
    dry = api.get(FINAL.format(c.id)).json()["data"]
    assert dry["available"] is False
    assert [b["code"] for b in dry["blockers"]] == ["UNDECIDED_POINTS"]
    assert dry["blockers"][0]["message"] == "1 point still needs Legal's decision."
    r = api.post(FINAL.format(c.id))
    assert r.status_code == 409 and r.json()["error"]["code"] == "FINAL_COPY_NOT_READY"
    assert db.scalar(select(M.DocumentVersion.id).where(
        M.DocumentVersion.contract_id == c.id, M.DocumentVersion.version_number == 2)) is None


def test_an_unfinished_review_blocks_the_final_copy(api, db, owner, tmp_path):
    c = _contract(db, owner)
    _ingest(db, tmp_path, c, _docx(*OURS), "ours.docx")         # no Review yet
    dry = api.get(FINAL.format(c.id)).json()["data"]
    assert [b["code"] for b in dry["blockers"]] == ["ANALYSIS_NOT_FINISHED"]


def test_the_final_contract_gate_names_the_final_contract():
    from legalmind.api.errors import ReplyUndecided
    gate = {"reason": "UNDECIDED_POINTS", "open_points": [{}, {}], "final": True}
    e = ReplyUndecided(gate)
    assert str(e) == ("The final contract cannot leave LegalMind yet: 2 points in its "
                      "review still need a decision.")
    assert "final" not in e.extra
    assert str(ReplyUndecided({**gate, "final": False})).startswith("This reply")


@pytest.mark.skipif(not __import__("os").environ.get("LEGALMIND_SOFFICE"),
                    reason="LEGALMIND_SOFFICE is not set: no LibreOffice here")
def test_a_final_copy_pdf_is_checked_before_it_is_stored(api, db, owner, tmp_path,
                                                         monkeypatch):
    """`FINAL-PACKAGE-SPEC` (e), S1: a final copy's PDF passes the PDF checks a created
    contract's does (PDF/A-2b, fonts, nothing but links …) and records its export
    options; a refused check stores nothing and says why. Paper we did not generate
    (no ContractDraft: provenance) is checked as a file and for its text — our margin and
    page footer are not its layout — and the record says so."""
    from legalmind.drafting import pdf, preflight

    def final() -> dict:
        c = _contract(db, owner)
        _ingest(db, tmp_path, c, _docx(*OURS), "ours.docx")
        r = api.post(FINAL.format(c.id))
        assert r.status_code == 201, r.text
        return db.get(M.DocumentVersion, uuid.UUID(
            r.json()["data"]["document_version"]["id"])).doc_metadata["pdf"]
    rec = final()
    assert (rec["status"], rec["kind"], rec["pdf_export"]) == ("READY", "final",
                                                             pdf.EXPORT)
    assert rec["checks"] == ["pdf_file", "text_equal"]
    monkeypatch.setattr(preflight, "pdf_file",
                        lambda data: [preflight.Problem("PDFA", "not PDF/A-2b")])
    rec = final()                  # the same file, the check refusing
    assert rec["status"] == "FAILED" and "not PDF/A-2b" in rec["error"]
    assert "storage_key" not in rec


def test_a_client_pdf_with_hidden_content_blocks_the_final_copy(api, db, owner, tmp_path):
    """S1 M2: a final copy of a PDF is that PDF as it came — so a comment, a form, a
    script, an attachment or a password in it blocks the final, in plain words, in the
    dry run and on Prepare. Not being PDF/A does not: we cannot convert their PDF."""
    import pymupdf

    from legalmind.ingestion.service import ingest_document
    from legalmind.ingestion.storage import LocalFilesystemStorage

    def pdf(dirty: bool) -> bytes:
        doc = pymupdf.open()
        page = doc.new_page()
        for i, line in enumerate(OURS):
            page.insert_text((72, 100 + 20 * i), line, fontsize=10)
        if dirty:
            page.add_text_annot((72, 300), "a note")
            doc.xref_set_key(doc.pdf_catalog(), "OpenAction",
                             "<</S/JavaScript/JS(app.alert(1))>>")
        return doc.tobytes()

    def plan(data: bytes) -> tuple:
        c = _contract(db, owner)
        v = ingest_document(db, LocalFilesystemStorage(tmp_path / "objects"),
                            contract_id=c.id, uploaded_by=owner.id, data=data,
                            filename="ours.pdf", declared_mime="application/pdf"
                            ).document_version
        v.doc_metadata = {**(v.doc_metadata or {}), "version_role": "COMPANY_DRAFT"}
        db.flush()
        _review(db, v, [])
        return api.get(FINAL.format(c.id)).json()["data"], api.post(FINAL.format(c.id))
    dry, made = plan(pdf(dirty=True))
    assert not dry["available"] and [b["message"] for b in dry["blockers"]] == [
        "The client's PDF contains comments or other annotations; ask for a clean PDF "
        "or upload the Word file.",
        "The client's PDF contains JavaScript; ask for a clean PDF or upload the Word "
        "file.",
        "The client's PDF does something when it is opened, beyond showing a page; ask "
        "for a clean PDF or upload the Word file."]
    assert made.status_code == 409
    assert made.json()["error"]["code"] == "FINAL_COPY_NOT_READY"
    dry, made = plan(pdf(dirty=False))
    assert dry["available"] and made.status_code == 201, made.text


def test_an_unreadable_version_is_never_said_to_be_still_reading(api, db, owner, tmp_path):
    """S1 verifier: a version that could not be read (here a PDF behind a password)
    blocks the final copy in plain words — what is wrong and what to do — and is never
    "still being read"."""
    import pymupdf

    from legalmind.ingestion.service import ingest_document
    from legalmind.ingestion.storage import LocalFilesystemStorage

    doc = pymupdf.open()
    doc.new_page().insert_text((72, 100), OURS[0], fontsize=10)
    locked = doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="o", user_pw="u")
    c = _contract(db, owner)
    v = ingest_document(db, LocalFilesystemStorage(tmp_path / "objects"), contract_id=c.id,
                        uploaded_by=owner.id, data=locked, filename="theirs.pdf",
                        declared_mime="application/pdf").document_version
    assert v.processing_status is E.ProcessingStatus.FAILED
    dry = api.get(FINAL.format(c.id)).json()["data"]
    assert dry["blockers"] == [{"code": "UNREADABLE", "message": "Version 1 is a "
                                "password-protected PDF, so it cannot be the final "
                                "contract. Ask the client for a copy without a password, "
                                "or upload the Word file."}]
    v.doc_metadata = {**(v.doc_metadata or {}), "unreadable": "CORRUPT"}
    db.flush()
    assert api.get(FINAL.format(c.id)).json()["data"]["blockers"][0]["message"] == (
        "Version 1 could not be read, so it cannot be the final contract. Upload a "
        "readable copy or the Word file.")
    assert api.post(FINAL.format(c.id)).status_code == 409


def test_a_counter_proposal_goes_to_the_client_before_the_final_copy(
        api, db, owner, tmp_path, monkeypatch):
    """Verifier item 1: answers that keep or propose our wording go back as our reply
    first (REPLY_FIRST); once the client accepts that reply, its final copy is clean —
    every tracked change accepted, no revision mark left."""
    monkeypatch.delenv("LEGALMIND_SOFFICE", raising=False)
    c, _, theirs = _negotiated(api, db, owner, tmp_path)
    assert api.get(FINAL.format(c.id)).json()["data"]["blockers"][0]["code"] == "CHANGES"
    for change in _changes(api, c)["changes"]:
        _answer(api, c, change, "accept_theirs" if change["clause"]["number"] == "4"
                else "keep_ours")
    dry = api.get(FINAL.format(c.id)).json()["data"]
    assert [b["code"] for b in dry["blockers"]] == ["REPLY_FIRST"]
    reply = api.post(f"{V1}/contracts/{c.id}/reply")
    assert reply.status_code == 201, reply.text
    after = api.get(FINAL.format(c.id)).json()["data"]
    assert after["available"] and len(after["agreed"]) == 5       # the round's answers
    r = api.post(FINAL.format(c.id))          # the client accepted our reply as it was
    assert r.status_code == 201, r.text
    v = db.get(M.DocumentVersion, uuid.UUID(r.json()["data"]["document_version"]["id"]))
    assert v.doc_metadata["final_copy_of"] == reply.json()["data"]["document_version"]["id"]
    from legalmind.api.storage import get_storage
    data = api.app.dependency_overrides.get(get_storage, get_storage)().get(v.storage_key)
    assert clean.has_markup(data) == []
    assert _text(data) == [*OURS[:3], THEIRS[2]]


def test_a_blank_left_to_fill_blocks_the_final_contract(api, db, owner, tmp_path):
    """Verifier item 4: a final contract never keeps a blank — a plain list says where."""
    c = _contract(db, owner)
    _ingest(db, tmp_path, c, _docx("1. Business Day means a day banks at ___________ are "
                                   "open.", *OURS[1:]), "ours.docx")
    dry = api.get(FINAL.format(c.id)).json()["data"]
    assert [b["code"] for b in dry["blockers"]] == ["BLANKS"]
    assert "clause 1 (" in dry["blockers"][0]["message"]
    assert api.post(FINAL.format(c.id)).status_code == 409


def test_a_client_pdf_with_answers_to_write_is_refused(api, db, owner):
    from tests.test_negotiation import _pair
    c = _contract(db, owner)
    _pair(db, c, "9. Liability is capped.", "9. Liability is uncapped.")
    _answer(api, c, _changes(api, c)["changes"][0], "keep_ours")
    dry = api.get(FINAL.format(c.id)).json()["data"]
    # a counter-proposal on the client's PDF: our reply first (which needs their Word file)
    assert dry["blockers"][0]["code"] in {"REPLY_FIRST", "NOT_READ"}


# ------------------------------------------------------------------ the decision
def test_a_final_copy_is_never_signed_after_our_changes(api, db, owner, tmp_path):
    """A2: on a final copy only Sign as is / Do not sign / On hold."""
    c = _contract(db, owner)
    _review(db, _ingest(db, tmp_path, c, _docx(*OURS), "ours.docx"), [])
    r = api.post(FINAL.format(c.id))
    v = db.get(M.DocumentVersion, uuid.UUID(r.json()["data"]["document_version"]["id"]))
    review = db.execute(select(M.Review).where(
        M.Review.document_version_id == v.id)).scalar() or _review(db, v, [])
    review.status = E.ReviewStatus.RESOLVED
    db.flush()
    assert CO.is_final_copy(db, review)
    with mock.patch.object(CO, "has_permission", return_value=True), \
            pytest.raises(InvalidTransition):
        CO.record(db, review, actor_id=owner.id, justification="x",
                  outcome=E.ContractOutcome.SIGN_WITH_CHANGES)


@pytest.mark.parametrize("text, blank", [
    ("banks at ___________are open", True), ("in the ___ months preceding", True),
    ("banks at ___Pune___are open", False), ("Clause __8___ of", False),
    ("effective as of ___1st_ day", False), ("the fee is [●] per month", True),
    ("within [ ] days", True), ("dated [•]", True), ("at .......... (the city)", True),
    ("Notice … … …", True), ("Definitions ........ 3", False), ("See clause [12]", False),
    ("as stated (i.e. ... and so on)", False), ("the fee is [*] per month", True),
    ("tick [X] if it applies", True), ("payable to [insert bank name]", True),
    ("the term is [TBD]", True), ("between <<Client Name>> and us", True),
    ("as in clause 4(b) [12] above", False), ("a << b and c >> d", True)])
def test_what_counts_as_a_blank(text, blank):
    """AM-323 r3 / AM-324 r3: a blank to fill, not a filled-in one or a dot leader."""
    from legalmind.api.routers.negotiation import blank_in
    assert (blank_in(text) is not None) is blank
