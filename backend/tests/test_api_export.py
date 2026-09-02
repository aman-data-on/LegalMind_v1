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
    assert "Findings" in text


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
    """LEGAL-02 in the file exactly as on the wire: a plain USER (no
    ``legal_position.view``) exports a file with the Company Standard value and
    rule outcome ABSENT — not blanked, not placeholdered."""
    owner = make_user(db)
    grant_role(db, owner, P.ROLE_USER)
    review = _analysed_review(db, owner, requirement_version)
    sign_in(api, db, owner)
    text = _docx_text(api.post(f"{V1}/reviews/{review.id}/export",
                               json={"format": "docx"}).content)
    assert "Company Standard" not in text
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
    assert "Company Standard" in text
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
