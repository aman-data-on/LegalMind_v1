"""Review export — 49.3's export row, formats per the owner's 2026-08-31
directive (PDF, DOCX).

The confidentiality property under test is the LEGAL-02 one: the export is
assembled from the caller's own serializations, so a caller without
``legal_position.view`` gets a file with the internal legal position fields
ABSENT — exactly as the API omits them on the wire.
"""

from __future__ import annotations

import io
import zipfile

from sqlalchemy import select

from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.security import permissions as P
from tests.conftest import (
    bespoke_role,
    grant,
    grant_role,
    make_evaluation,
    make_finding,
    make_review_for,
    make_user,
    sign_in,
    without_legal_position,
)

V1 = "/api/v1"


def _analysed_review(db, owner, requirement_version):
    review = make_review_for(db, owner)
    finding = make_finding(db, review, requirement_version)
    evaluation = make_evaluation(
        db, finding, rule_outcome=E.RuleOutcome.UNACCEPTABLE)
    evaluation.expected_value = {"duration_months": 12, "basis": "FEES_PAID"}
    evaluation.actual_value = {"duration_months": 36, "basis": "FEES_PAID"}
    db.flush()
    return review


def _docx_text(content: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        return archive.read("word/document.xml").decode("utf-8")


def test_export_requires_export_generate(api, db, seeded, requirement_version):
    viewer = make_user(db)
    # Every permission the route path touches EXCEPT export.generate.
    grant(db, viewer, bespoke_role(
        db, "NO_EXPORT",
        [P.CONTRACT_VIEW, P.REVIEW_VIEW, P.REPORT_VIEW, P.FINDING_VIEW]))
    review = _analysed_review(db, viewer, requirement_version)
    sign_in(api, db, viewer)
    response = api.post(f"{V1}/reviews/{review.id}/export",
                        json={"format": "pdf"})
    assert response.status_code == 403


def test_export_pdf_is_a_pdf_attachment(api, db, seeded, requirement_version):
    owner = make_user(db)
    grant_role(db, owner, P.ROLE_USER)
    review = _analysed_review(db, owner, requirement_version)
    sign_in(api, db, owner)
    response = api.post(f"{V1}/reviews/{review.id}/export",
                        json={"format": "pdf"})
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment" in response.headers["Content-Disposition"]
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_export_docx_is_a_docx_attachment(api, db, seeded, requirement_version):
    owner = make_user(db)
    grant_role(db, owner, P.ROLE_USER)
    review = _analysed_review(db, owner, requirement_version)
    sign_in(api, db, owner)
    response = api.post(f"{V1}/reviews/{review.id}/export",
                        json={"format": "docx"})
    assert response.status_code == 200
    assert response.content.startswith(b"PK")  # OOXML zip container
    text = _docx_text(response.content)
    assert "DEVIATION" in text
    assert "The points that need action, in detail" in text   # AB-103: the structure


def test_export_rejects_an_unknown_format(api, db, seeded, requirement_version):
    owner = make_user(db)
    grant_role(db, owner, P.ROLE_USER)
    review = _analysed_review(db, owner, requirement_version)
    sign_in(api, db, owner)
    response = api.post(f"{V1}/reviews/{review.id}/export",
                        json={"format": "xlsx"})
    assert response.status_code == 422


def test_export_omits_legal_position_fields_without_the_permission(
        api, db, seeded, requirement_version):
    """LEGAL-02 in the file exactly as on the wire: an account without
    ``legal_position.view`` exports a file with the Company Standard value and
    rule outcome ABSENT — not blanked, not placeholdered. (A Department User
    holds the grant since AB-12 r7, so it is removed here to exercise the gate.)"""
    owner = make_user(db)
    grant_role(db, owner, P.ROLE_USER)
    without_legal_position(db, owner)
    review = _analysed_review(db, owner, requirement_version)
    sign_in(api, db, owner)
    text = _docx_text(api.post(f"{V1}/reviews/{review.id}/export",
                               json={"format": "docx"}).content)
    assert "Our standard" not in text
    assert "Rule outcome" not in text
    assert "duration_months: 12" not in text
    # What the caller CAN see is present.
    assert "duration_months: 36" in text


def test_export_includes_the_standard_for_a_legal_position_holder(
        api, db, seeded, requirement_version):
    owner = make_user(db)
    grant_role(db, owner, P.ROLE_USER)
    grant(db, owner, bespoke_role(db, "POSITION_HOLDER",
                                  [P.LEGAL_POSITION_VIEW]))
    review = _analysed_review(db, owner, requirement_version)
    sign_in(api, db, owner)
    text = _docx_text(api.post(f"{V1}/reviews/{review.id}/export",
                               json={"format": "docx"}).content)
    assert "Our standard" in text
    assert "duration_months: 12" in text


def test_export_writes_an_audit_event(api, db, seeded, requirement_version):
    owner = make_user(db)
    grant_role(db, owner, P.ROLE_USER)
    review = _analysed_review(db, owner, requirement_version)
    sign_in(api, db, owner)
    api.post(f"{V1}/reviews/{review.id}/export", json={"format": "pdf"})
    event = db.execute(
        select(M.AuditEvent).where(M.AuditEvent.action == "report.exported")
    ).scalars().first()
    assert event is not None
    assert str(event.entity_id) == str(review.id)
    assert event.after_state["format"] == "pdf"


# ---- AB-103 (owner, 2026-10-22): the report a reader downloads — and previews -------
def _decided_review(api, db, requirement_version):
    """A synthetic review with one point decided "change needed" by a designated
    reviewer — the owner exports it."""
    from tests.test_review_assignment import _reviewer
    owner = make_user(db)
    grant_role(db, owner, P.ROLE_USER)
    review = _analysed_review(db, owner, requirement_version)
    review.status = E.ReviewStatus.LEGAL_REVIEW
    evaluation = db.execute(select(M.Evaluation).join(M.Finding).where(
        M.Finding.review_id == review.id)).scalars().one()
    db.flush()
    sign_in(api, db, _reviewer(db))
    assert api.post(f"{V1}/evaluations/{evaluation.id}/decisions", json={
        "decision_type": "REQUIRE_COMPANY_STANDARD", "expected_version": 0,
        "justification": "send our 12-month cap wording"}).status_code == 201
    sign_in(api, db, owner)
    return review


def test_the_report_reads_in_the_order_a_reader_needs(api, db, seeded, requirement_version):
    review = _decided_review(api, db, requirement_version)
    text = _docx_text(api.post(f"{V1}/reviews/{review.id}/export",
                               json={"format": "docx"}).content)
    order = ["Summary", "Next steps", "At a glance", "Changes to send to the client (1)",
             "The points that need action, in detail", "Appendix — audit record"]
    positions = [text.find(s) for s in order]
    assert -1 not in positions and positions == sorted(positions), positions
    assert "send our 12-month cap wording" in text                  # the reason travels
    assert "Change requested — our wording to send" in text         # words, not codes
    assert "REQUIRE_COMPANY_STANDARD" not in text


def test_the_preview_is_the_downloaded_report(api, db, seeded, requirement_version):
    review = _decided_review(api, db, requirement_version)
    blocks = api.get(f"{V1}/reviews/{review.id}/report/document").json()["data"]
    headings = [b["text"] for b in blocks if b["kind"] in ("h1", "h2", "h3")]
    text = _docx_text(api.post(f"{V1}/reviews/{review.id}/export",
                               json={"format": "docx"}).content)
    assert headings and all(h.replace("&", "&amp;") in text for h in headings)
    assert headings[1] == "Summary"


def test_the_preview_withholds_the_standard_exactly_as_the_file_does(
        api, db, seeded, requirement_version):
    owner = make_user(db)
    grant_role(db, owner, P.ROLE_USER)
    without_legal_position(db, owner)
    review = _analysed_review(db, owner, requirement_version)
    sign_in(api, db, owner)
    blocks = api.get(f"{V1}/reviews/{review.id}/report/document").json()["data"]
    assert not any(b["label"] == "Our standard" for b in blocks)
    assert any("36" in b["text"] for b in blocks)


def test_stored_values_are_said_in_words():
    from legalmind.api.export_render import _plain
    assert _plain({"presence": "PRESENT"}, standard=True) == "Required"
    assert _plain({"presence": "ABSENT"}) == "Not in the contract"
    assert _plain({"allowed_values": ["PUNE", "BOMBAY_HIGH_COURT"]}) == "Pune or Bombay High Court"
    assert _plain({"cap_value": 6, "cap_unit": "MONTHS"}) == "6 months"
    assert _plain({"duration_months": 12}) == "duration_months: 12"     # unknown: verbatim


def test_every_page_says_what_it_is_and_that_it_is_confidential(
        api, db, seeded, requirement_version):
    import pymupdf
    review = _decided_review(api, db, requirement_version)
    pdf = pymupdf.open(stream=api.post(f"{V1}/reviews/{review.id}/export",
                                       json={"format": "pdf"}).content, filetype="pdf")
    for index in range(pdf.page_count):
        text = pdf[index].get_text()
        assert "contract review report" in text
        assert (f"Confidential · internal legal review · Page {index + 1} of "
                f"{pdf.page_count}") in text
    content = api.post(f"{V1}/reviews/{review.id}/export", json={"format": "docx"}).content
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        parts = " ".join(archive.read(n).decode() for n in archive.namelist()
                         if n.startswith(("word/header", "word/footer")))
    assert "contract review report" in parts and "NUMPAGES" in parts


def test_points_carry_one_number_across_tables_and_detail(
        api, db, seeded, requirement_version):
    review = _decided_review(api, db, requirement_version)
    blocks = api.get(f"{V1}/reviews/{review.id}/report/document").json()["data"]
    table = next(b for b in blocks if b["kind"] == "table"
                 and b["rows"][0][0] == "Point" and b["rows"][0][3] == "The contract says")
    numbered = table["rows"][1][0]
    assert numbered.startswith("1. ")
    assert any(b["kind"] == "h3" and b["text"] == numbered for b in blocks)


def test_clauses_no_standard_covers_are_summarised_by_section():
    from legalmind.api.export_render import build_export_model
    unmatched = [{"section_number": "1", "section_title": "DEFINITIONS", "page_number": 2,
                  "excerpt": "1. DEFINITIONS"},
                 *[{"section_number": f"1.{i}", "page_number": 2 + i // 5,
                    "excerpt": f"1.{i} a definition"} for i in range(1, 12)],
                 {"section_number": "7.2", "page_number": 8, "excerpt": "7.2 something"}]
    blocks = build_export_model(contract={"name": "C"}, version={}, review={},
                                report={"unmatched_provisions_detail": unmatched},
                                findings=[], exported_at="2026-10-22T10:00:00")
    lines = [b.text for b in blocks if b.kind == "bullet"]
    assert lines == ["§1 Definitions — 12 clauses, p.2-4", "§7 — 1 clause, p.8"]


def test_why_a_standard_was_not_measured_is_said_in_words():
    from legalmind.api.export_render import _why_not
    assert _why_not({"outcome": "NOT_APPLICABLE", "reason": "a MSA is not measured against "
                     "the §31.9 VENDOR_AGREEMENT position (AM-147/AM-153)"}) == (
        "Written for vendor agreements — not this type of contract")
    assert _why_not({"outcome": "SAME_POSITION", "reason": "x"}).startswith("Measured once")
    assert _why_not({"outcome": "NOT_APPLICABLE", "reason": "something new"}) == "something new"


def test_the_summary_and_next_steps_come_from_the_record():
    """The first page answers "where are we, what next, who" from the record alone:
    changes to send most important first, nothing invented (owner, 2026-10-22)."""
    from legalmind.api.export_render import build_export_model

    def point(n, decision=None, status="RESOLVED", user_status="DEVIATION"):
        return {"id": f"f{n}", "requirement_code": f"R-{n}", "status": status,
                "user_status": user_status, "evidence": [], "evaluations": []}
    findings = [point(1), point(2), point(3, status="OPEN", user_status="ACCEPTABLE")]
    report = {
        "user_status_counts": {"ACCEPTABLE": 1, "DEVIATION": 2},
        "decisions": [{"finding_id": "f1", "decision_type": "REQUIRE_COMPANY_STANDARD",
                       "justification": "ask"},
                      {"finding_id": "f2", "decision_type": "REJECT",
                       "justification": "must"}],
        "progress": {"stage": "COMPLETE", "required": 2, "to_decide": 0,
                     "clarification": 0, "assignee": {"name": "Rita"},
                     "decided_by_type": {"REQUIRE_COMPANY_STANDARD": 1, "REJECT": 1}},
        "contract_outcome": {"history": [{"outcome": "SIGN_WITH_CHANGES",
                                          "decided_by_name": "Rita",
                                          "justification": "send them"}]}}
    blocks = build_export_model(contract={"name": "C", "owner_name": "Omar",
                                          "client_name": "Client Co"},
                                version={}, review={}, report=report, findings=findings,
                                exported_at="2026-10-22T10:00:00")
    text = [b.text for b in blocks]
    assert "Client Co" in text and "Omar" in text
    assert "1. Omar sends the 2 changes listed below to the client." in text
    changes = next(b for b in blocks if b.kind == "table" and b.rows[0][1] == "Change")
    assert [r[1] for r in changes.rows[1:]] == ["Must change", "Requested"]
    assert changes.rows[1][3] == "Missing — to be added"
    # a match is listed, never detailed
    details = [b.text for b in blocks if b.kind == "h3"]
    assert len(details) == 2 and not any("R-3" in d for d in details)


# ---- owner, 2026-10-27: what the client changed, said plainly -----------------------
_MARKED = {"changes": 3, "clauses": 2, "measured": 1, "unmeasured": 1, "notes": 1,
           "sections": [
               {"section": "7", "title": "TERM AND TERMINATION", "page": 6,
                "measured_by": ["Termination notice"], "notes": [],
                "changes": [
                    {"clause": "7.2", "kind": "Changed", "removed": "ninety (90) days",
                     "added": "thirty (30) days", "measured_by": ["Termination notice"]},
                    {"clause": "7.5", "kind": "Added", "removed": "",
                     "added": "No fee applies on exit.", "measured_by": []}]},
               {"section": "11", "title": None, "page": 9, "measured_by": [],
                "notes": [{"clause": "11.2", "author": "Their counsel",
                           "text": "Please confirm the data location."}],
                "changes": [
                    {"clause": "11.2", "kind": "Removed", "removed": "the data of",
                     "added": "", "measured_by": []}]}]}


def _marked_blocks():
    from legalmind.api.export_render import build_export_model
    return build_export_model(
        contract={"name": "C"}, version={}, review={}, report={}, findings=[],
        exported_at="2026-10-27T10:00:00",
        angles={"client_changes": _MARKED,
                "recommendation": "Recommendation: do not sign as drafted (§25.1)."})


def test_a_marked_up_contract_lists_every_change_in_plain_words():
    blocks = _marked_blocks()
    heads = [b.text for b in blocks if b.kind in ("h2", "h3")]
    assert "The client's changes (2 clauses)" in heads
    assert "§7 Term and termination" in heads and "§11" in heads   # sentence case
    changes = [b for b in blocks if b.kind == "change"]
    assert [b.rows[0][:2] for b in changes] == [("7.2", "Changed"), ("7.5", "Added"),
                                               ("11.2", "Removed")]
    # "Please read" only where it tells changes apart: §7 is mixed, §11 is all to read
    assert [b.rows[0][4] for b in changes] == ["", "read", ""]
    assert changes[0].text == "7.2 · Changed: “ninety (90) days” → “thirty (30) days”"
    note = next(b for b in blocks if b.kind == "quote" and "data location" in b.text)
    assert note.label == "Their note on 11.2 (Their counsel)"
    said = " ".join(b.text for b in blocks)
    assert "172" not in said and "3 changes to 2 clauses" in said
    assert "§25.1" not in said                       # no rulebook numbers for a reader


def test_an_unmarked_contract_has_no_changes_section():
    from legalmind.api.export_render import build_export_model
    blocks = build_export_model(contract={"name": "C"}, version={}, review={},
                                report={}, findings=[], exported_at="2026-10-27T10:00:00",
                                angles={})
    assert not any(b.kind == "change" or "client's changes" in b.text for b in blocks)
