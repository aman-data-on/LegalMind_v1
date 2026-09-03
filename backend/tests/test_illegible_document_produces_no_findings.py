"""A document nobody can read produces NO legal conclusions — 34.9, Step 30 r13.

This is the safety property behind the 2026-09-03 extraction fix, and the reason
that fix was worth making. On the live instance, a PDF whose embedded fonts
carried an incorrect `/ToUnicode` CMap extracted as glyph codes —

    "MaVWeU SeUYLceV AgUeePeQW"   for   "Master Services Agreement"

— cleared the presence-only usable-text check, and a Review then reported
**3 MATCH, 7 MISSING and 4 UNABLE_TO_EVALUATE against text nobody could read.**
A MATCH is an assertion that the document agrees with a ratified Company
Standard. Three of them were drawn from mojibake.

The unit-level behaviour lives in `test_extraction_legibility.py`. What is pinned
here is the consequence that actually matters, through the real pipeline: ingest
→ evidence → clause loading → analysis. Two distinct wrong answers must both be
impossible:

  * MATCH / DEVIATION — a legal conclusion about unreadable text;
  * MISSING — which asserts the provision is ABSENT from the document, when the
    truth is that the document could not be read at all.

The correct outcome is neither: `ANALYSIS_FAILED` with no Findings, which is what
`run_analysis` already does when no clause carries usable text. This test exists
so that pairing cannot silently come apart — it would pass today for the right
reason, and fail the moment either half regresses.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from legalmind.analysis.service import run_analysis
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.ingestion.service import ingest_document
from legalmind.ingestion.storage import LocalFilesystemStorage
from legalmind.ingestion.validation import PDF_MIME
from tests.conftest import make_user

# The Requirement configuration is REUSED from `test_analysis.py` rather than
# restated: that config is already proven to reach a real verdict, so the only
# variable between the two tests below is whether the text is legible. A
# hand-rolled copy here could fail to match for its own reasons and make "no
# findings" look like a refusal when it was really a no-op.
from tests.test_analysis import (
    LEGAL_RULE,
    MAPPING,
    STANDARD,
    Builder,
)
from tests.test_extraction_legibility import LEGAL_PROSE, build_pdf, mangle


@pytest.fixture
def storage(tmp_path):
    return LocalFilesystemStorage(tmp_path / "objects")


@pytest.fixture
def build(db, storage):
    return Builder(db, storage, make_user(db))


def _review_over_pdf(build, pdf_bytes):
    """`Builder.review` but with PDF bytes — the format the defect lives in.

    A DOCX cannot reproduce it: its text comes from the document XML, so no font
    encoding is involved and the bug is structurally impossible there.
    """
    db = build.db
    contract = M.Contract(owner_id=build.owner.id, name="Uploaded MSA",
                          contract_type="MSA", status=E.ContractStatus.ACTIVE)
    db.add(contract); db.flush()
    result = ingest_document(db, build.storage, contract_id=contract.id,
                             uploaded_by=build.owner.id, data=pdf_bytes,
                             filename="msa.pdf", declared_mime=PDF_MIME)
    review = M.Review(contract_id=contract.id,
                      document_version_id=result.document_version.id,
                      configuration_snapshot_id=build.snapshot.id,
                      status=E.ReviewStatus.DRAFT, created_by=build.owner.id)
    db.add(review); db.flush()
    return review, result.document_version


def _findings(db, review):
    return db.execute(select(M.Finding)
                      .where(M.Finding.review_id == review.id)).scalars().all()


# One page, used verbatim by both tests — the second one mangled. It carries the
# phrases `MAPPING` confirms on and the cap `STANDARD` compares against, so the
# readable form reaches a real verdict.
#
# Long enough to clear `MIN_WORDS_TO_JUDGE_LEGIBILITY`, which is load-bearing:
# see `test_a_document_too_short_to_judge_is_left_alone` for the limitation that
# cutoff deliberately accepts.
READABLE_PAGE = (
    "1. Limitation of Liability. "
    "Liability shall not exceed 6 months of fees paid. "
) + LEGAL_PROSE[:1600]


def test_a_readable_document_does_reach_a_verdict(build, db, monkeypatch):
    """The control. Without it, "no Findings" below would prove nothing — it
    could just as easily mean the configuration never matched anything."""
    from legalmind.ingestion import parsing
    monkeypatch.setattr(parsing, "ocr_available", lambda: False)

    build.requirement("LIABILITY-001", E.EvaluatorType.NUMERIC_COMPARISON,
                      mapping=MAPPING, standard=STANDARD, legal_rule=LEGAL_RULE)
    review, version = _review_over_pdf(build, build_pdf([READABLE_PAGE]))

    assert version.extraction_status is E.ExtractionStatus.COMPLETE
    run = run_analysis(db, review)
    assert run.findings_created == 1, f"control produced no finding: {run.failures}"
    assert _findings(db, review)
    assert review.status is not E.ReviewStatus.ANALYSIS_FAILED


def test_an_illegible_document_produces_no_findings_at_all(build, db, monkeypatch):
    """The property. Identical page, identical configuration — only the font
    mapping is broken. No MATCH, no DEVIATION, and no MISSING either."""
    from legalmind.ingestion import parsing
    monkeypatch.setattr(parsing, "ocr_available", lambda: False)

    build.requirement("LIABILITY-001", E.EvaluatorType.NUMERIC_COMPARISON,
                      mapping=MAPPING, standard=STANDARD, legal_rule=LEGAL_RULE)
    review, version = _review_over_pdf(build, build_pdf([mangle(READABLE_PAGE)]))

    # The extraction refused rather than returning the glyph stream.
    assert version.extraction_status is E.ExtractionStatus.FAILED

    run = run_analysis(db, review)

    # Nothing was concluded. This is the whole point: on the live instance this
    # same shape of document yielded 3 MATCH findings.
    assert run.findings_created == 0
    assert _findings(db, review) == []
    assert review.status is E.ReviewStatus.ANALYSIS_FAILED


def test_no_evidence_row_carries_the_unreadable_text(build, db, monkeypatch):
    """Nothing downstream can cite, index, embed or quote what was refused —
    the mojibake must not be persisted at all, on any surface.

    `document_evidence` is the single source every one of them reads: the
    document pane, a Finding's `evidence_refs`, a citation's chunk, and the
    retrieval index. An empty set here is what makes the guarantee total rather
    than per-surface.
    """
    from legalmind.ingestion import parsing
    monkeypatch.setattr(parsing, "ocr_available", lambda: False)

    _, version = _review_over_pdf(build, build_pdf([mangle(READABLE_PAGE)]))

    rows = db.execute(
        select(M.DocumentEvidence)
        .where(M.DocumentEvidence.document_version_id == version.id)
    ).scalars().all()
    assert rows == []


def test_a_document_too_short_to_judge_is_left_alone(build, db, monkeypatch):
    """The limitation this fix deliberately accepts, pinned so it is visible.

    Under `MIN_WORDS_TO_JUDGE_LEGIBILITY` there is not enough text to tell
    garbling from a legitimately noun-heavy page — a cover sheet, a signature
    page or a website footer scores just as low, and those were measured at
    0.055-0.086 on the real corpus. Acting on that little evidence would send
    correctly-extracted pages to OCR and make good documents worse, which is the
    more expensive mistake.

    So a very short garbled document still extracts as glyph codes. Recorded as
    a known bound rather than a surprise: every real contract is far longer, and
    the document that prompted the fix carried ~1,960 characters on page one
    alone. Tightening this needs a signal that works on 40 words, not a lower
    threshold on this one.
    """
    from legalmind.ingestion import parsing
    monkeypatch.setattr(parsing, "ocr_available", lambda: False)

    short = "Liability shall not exceed 6 months of fees paid."
    _, version = _review_over_pdf(build, build_pdf([mangle(short)]))

    # Unjudgeable, so the parser did not intervene — and says so by NOT having
    # recorded a legibility diagnostic.
    assert parsing.text_is_legible(mangle(short)) is None
    assert version.extraction_status is not E.ExtractionStatus.FAILED


def test_the_upload_endpoint_still_succeeds_and_reports_the_real_state(
        api, db, seeded, user, tmp_path, monkeypatch):
    """The failure path a person actually meets.

    An illegible document must not make the upload itself fail: the request
    succeeds, the version is recorded with its true `extraction_status`, and the
    workspace can then say honestly that nothing could be read. A 500 here would
    look like a broken product rather than an unreadable file — and indexing must
    stay quiet too, which it does by returning "extraction failed" rather than
    raising (`assist/indexing.py`).
    """
    from legalmind.ingestion import parsing
    from tests.conftest import grant_role, sign_in
    monkeypatch.setattr(parsing, "ocr_available", lambda: False)

    grant_role(db, user, "USER")
    sign_in(api, db, user)
    contract_id = api.post("/api/v1/contracts",
                           json={"name": "Broken fonts", "contract_type": "MSA"}
                           ).json()["data"]["id"]

    uploaded = api.post(f"/api/v1/contracts/{contract_id}/document-versions",
                        content=build_pdf([mangle(READABLE_PAGE)]),
                        headers={"content-type": PDF_MIME,
                                 "x-filename": "broken.pdf"})
    assert uploaded.status_code == 201, uploaded.text

    # Both statuses report FAILED, and they are separate axes on purpose (34.15):
    # the processing RUN failed because extraction produced nothing usable.
    version = uploaded.json()["data"]["document_version"]
    assert version["processing_status"] == "FAILED"
    assert version["extraction_status"] == "FAILED"

    # Nothing to read, and nothing to cite — the two surfaces the workspace uses.
    evidence = api.get(f"/api/v1/document-versions/{version['id']}/evidence")
    assert evidence.status_code == 200
    assert evidence.json()["data"] == []
