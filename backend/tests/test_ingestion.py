"""Document ingestion tests — locked Step 34.

The rule under most of these is locked 34.9: **extraction failures never result
in invented text or legal conclusions.**
"""

from __future__ import annotations

import io
import zipfile

import pytest

from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.ingestion import parsing
from legalmind.ingestion.service import (
    ingest_document,
    process_document_version,
)
from legalmind.ingestion.storage import LocalFilesystemStorage, fingerprint
from legalmind.ingestion.validation import (
    DOCX_MIME,
    PDF_MIME,
    UploadRejected,
    validate_upload,
)
from tests.conftest import make_user


@pytest.fixture
def storage(tmp_path):
    return LocalFilesystemStorage(tmp_path / "objects")


@pytest.fixture
def contract(db):
    owner = make_user(db)
    c = M.Contract(owner_id=owner.id, name="ACME MSA",
                   status=E.ContractStatus.ACTIVE)
    db.add(c); db.flush()
    c._owner = owner
    return c


# ----------------------------------------------------------------- builders
def build_pdf(pages: list[str]) -> bytes:
    import pymupdf
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page()
        page.insert_text((72, 96), text, fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


def build_docx(paragraphs: list[str], table: list[list[str]] | None = None) -> bytes:
    import docx
    d = docx.Document()
    for p in paragraphs:
        d.add_paragraph(p)
    if table:
        t = d.add_table(rows=len(table), cols=len(table[0]))
        for r, row in enumerate(table):
            for c, val in enumerate(row):
                t.cell(r, c).text = val
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def build_image_only_pdf() -> bytes:
    """A PDF page with no text layer — the scanned-document case (34.3)."""
    import pymupdf
    doc = pymupdf.open()
    doc.new_page()          # blank page, no text
    data = doc.tobytes()
    doc.close()
    return data


# ================================================================ validation
def test_rejects_unsupported_type(db):
    with pytest.raises(UploadRejected) as e:
        validate_upload(b"plain text", "notes.txt", "text/plain")
    assert e.value.code == "UNSUPPORTED_TYPE"


def test_rejects_content_type_mismatch(db):
    """34.16 — the client's declared type is never trusted."""
    docx_bytes = build_docx(["hello"])
    with pytest.raises(UploadRejected) as e:
        validate_upload(docx_bytes, "trick.pdf", PDF_MIME)
    assert e.value.code == "CONTENT_TYPE_MISMATCH"


def test_rejects_zip_that_is_not_docx(db):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("evil.sh", "#!/bin/sh\n")
    with pytest.raises(UploadRejected) as e:
        validate_upload(buf.getvalue(), "x.docx", DOCX_MIME)
    assert e.value.code == "UNRECOGNISED_CONTENT"


def test_rejects_empty_file(db):
    with pytest.raises(UploadRejected) as e:
        validate_upload(b"", "empty.pdf", PDF_MIME)
    assert e.value.code == "EMPTY_FILE"


# =================================================================== storage
def test_original_is_preserved_byte_identical(storage):
    """34.5 / 34.18 — the ingestion layer must not alter the original."""
    data = build_pdf(["8.1 Term. This Agreement commences on the Effective Date."])
    key = storage.put(data, suggested_name="msa.pdf")
    assert storage.get(key) == data
    assert fingerprint(storage.get(key)) == fingerprint(data)


def test_storage_is_write_once(storage):
    """No update or overwrite operation exists (34.18)."""
    assert not hasattr(storage, "update")
    assert not hasattr(storage, "delete")
    data = b"%PDF-1.7 a"
    k1 = storage.put(data, suggested_name="a.pdf")
    k2 = storage.put(data, suggested_name="a.pdf")
    assert k1 != k2                 # identical content never collides
    assert storage.get(k1) == storage.get(k2) == data


# ================================================================= ingestion
def test_ingest_pdf_produces_evidence_with_locations(db, storage, contract):
    """34.11 / 34.13 — pages and source locations retained for Evidence."""
    data = build_pdf([
        "8.1 Limitation of Liability\n\nThe aggregate liability shall not exceed "
        "six months of fees paid under this Agreement.",
        "12.1 Governing Law\n\nThis Agreement is governed by the laws of India.",
    ])
    result = ingest_document(
        db, storage, contract_id=contract.id, uploaded_by=contract._owner.id,
        data=data, filename="msa.pdf", declared_mime=PDF_MIME)

    assert result.document_version.extraction_status is E.ExtractionStatus.COMPLETE
    assert result.document_version.processing_status is E.ProcessingStatus.COMPLETED
    assert result.evidence_count > 0

    evidence = db.query(M.DocumentEvidence).filter_by(
        processing_run_id=result.processing_run.id).all()
    assert {e.page_number for e in evidence} == {1, 2}
    assert all(e.source_type is E.EvidenceSourceType.NATIVE_TEXT for e in evidence)
    assert all(e.start_offset is not None for e in evidence)


def test_clause_numbering_is_preserved_not_invented(db, storage, contract):
    """34.12 — existing numbering preserved; nothing generated where absent.

    Uses DOCX because it has a real paragraph model; PDF text layout gives no
    reliable paragraph boundaries, so asserting paragraph-level segmentation
    against a synthetic PDF would test the fixture rather than the parser.
    """
    data = build_docx([
        "8.2 Limitation of Liability",
        "A paragraph with no clause number at all.",
        "Section 14 Governing Law",
    ])
    result = ingest_document(
        db, storage, contract_id=contract.id, uploaded_by=contract._owner.id,
        data=data, filename="msa.docx", declared_mime=DOCX_MIME)

    evidence = db.query(M.DocumentEvidence).filter_by(
        processing_run_id=result.processing_run.id).all()
    numbers = {e.section_number for e in evidence}
    assert "8.2" in numbers
    assert "14" in numbers
    assert None in numbers          # unnumbered text stays unnumbered


def test_original_text_preserved_alongside_normalized(db, storage, contract):
    """34.14 — both representations are kept."""
    data = build_docx(["8.1   Term.    Spacing    is   irregular."])
    result = ingest_document(
        db, storage, contract_id=contract.id, uploaded_by=contract._owner.id,
        data=data, filename="msa.docx", declared_mime=DOCX_MIME)
    e = db.query(M.DocumentEvidence).filter_by(
        processing_run_id=result.processing_run.id).first()
    assert "  " not in e.content                                    # normalized
    assert "   " in e.evidence_metadata["original_content"]         # original kept


def test_docx_tables_preserved_as_table_evidence(db, storage, contract):
    """34.11 — tables preserved where technically available."""
    data = build_docx(["1. Fees"], table=[["Item", "Amount"], ["Licence", "1000"]])
    result = ingest_document(
        db, storage, contract_id=contract.id, uploaded_by=contract._owner.id,
        data=data, filename="fees.docx", declared_mime=DOCX_MIME)
    kinds = {e.source_type for e in db.query(M.DocumentEvidence).filter_by(
        processing_run_id=result.processing_run.id).all()}
    assert E.EvidenceSourceType.TABLE in kinds


def test_version_numbers_are_system_controlled_and_sequential(db, storage, contract):
    """42.4 UNIQUE(contract_id, version_number); Step 33.6."""
    for expected in (1, 2, 3):
        r = ingest_document(
            db, storage, contract_id=contract.id, uploaded_by=contract._owner.id,
            data=build_pdf([f"Version {expected} text content here."]),
            filename="msa.pdf", declared_mime=PDF_MIME)
        assert r.document_version.version_number == expected


def test_duplicate_is_detected_not_silently_suppressed(db, storage, contract):
    """34.5 — duplicates are detectable. Whether a re-upload is a new
    contractual version is a business decision (Step 33.9), so ingestion
    reports the duplicate rather than deciding."""
    data = build_pdf(["8.1 Liability capped at six months of fees."])
    first = ingest_document(
        db, storage, contract_id=contract.id, uploaded_by=contract._owner.id,
        data=data, filename="msa.pdf", declared_mime=PDF_MIME)
    second = ingest_document(
        db, storage, contract_id=contract.id, uploaded_by=contract._owner.id,
        data=data, filename="msa-again.pdf", declared_mime=PDF_MIME)

    assert second.duplicate_of == first.document_version.id
    assert second.document_version.id != first.document_version.id
    assert second.document_version.file_hash == first.document_version.file_hash


def test_same_file_in_two_contracts_is_not_a_duplicate(db, storage, contract):
    """42.4 — file_hash is indexed but NOT globally unique: the same source file
    may legitimately appear in multiple contracts."""
    other = M.Contract(owner_id=contract._owner.id, name="Other MSA",
                       status=E.ContractStatus.ACTIVE)
    db.add(other); db.flush()
    data = build_pdf(["8.1 Liability capped at six months of fees."])

    ingest_document(db, storage, contract_id=contract.id,
                    uploaded_by=contract._owner.id, data=data,
                    filename="a.pdf", declared_mime=PDF_MIME)
    r2 = ingest_document(db, storage, contract_id=other.id,
                         uploaded_by=contract._owner.id, data=data,
                         filename="a.pdf", declared_mime=PDF_MIME)
    assert r2.duplicate_of is None


# ============================================== fail-closed extraction (34.9)
def test_no_text_layer_and_no_ocr_fails_closed(db, storage, contract, monkeypatch):
    """34.4 / 34.7 / 34.9 — the scanned-document case.

    With no native text and no OCR toolchain, extraction FAILS. It must not
    produce empty-but-successful evidence, because a Requirement evaluated
    against silently-missing text would yield a false MISSING rather than
    UNABLE_TO_EVALUATE (34.17).

    The absent toolchain is FORCED rather than assumed. This line used to read
    `assert parsing.ocr_available() is False  # documents this environment`,
    which passed only because no OCR was installed on the machine — so the test
    broke the moment one was (2026-09-03), while the property it names was still
    perfectly true. A test about "and no OCR" has to establish that itself.
    """
    monkeypatch.setattr(parsing, "ocr_available", lambda: False)
    result = ingest_document(
        db, storage, contract_id=contract.id, uploaded_by=contract._owner.id,
        data=build_image_only_pdf(), filename="scan.pdf", declared_mime=PDF_MIME)

    assert result.document_version.extraction_status is E.ExtractionStatus.FAILED
    assert result.document_version.processing_status is E.ProcessingStatus.FAILED
    assert result.processing_run.status is E.ProcessingRunStatus.FAILED
    assert result.processing_run.error_code == "EXTRACTION_FAILED"
    assert result.evidence_count == 0            # nothing invented
    assert any("OCR" in d for d in result.diagnostics)


def test_partial_extraction_is_explicitly_represented(db, storage, contract):
    """34.10 — a document where only some pages yield text."""
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 96), "8.1 Liability is capped at six months of fees.",
                     fontsize=11)
    doc.new_page()                               # second page: no text layer
    data = doc.tobytes()
    doc.close()

    result = ingest_document(
        db, storage, contract_id=contract.id, uploaded_by=contract._owner.id,
        data=data, filename="mixed.pdf", declared_mime=PDF_MIME)

    assert result.document_version.extraction_status is E.ExtractionStatus.PARTIAL
    assert result.processing_run.run_metadata["pages_failed"] == [2]
    assert result.evidence_count > 0             # page 1 still usable


def test_corrupt_pdf_fails_without_inventing_text(db, storage, contract):
    result = ingest_document(
        db, storage, contract_id=contract.id, uploaded_by=contract._owner.id,
        data=b"%PDF-1.7\nthis is not really a pdf body at all",
        filename="broken.pdf", declared_mime=PDF_MIME)
    assert result.document_version.extraction_status is E.ExtractionStatus.FAILED
    assert result.evidence_count == 0


def test_retry_creates_a_new_run_and_preserves_history(db, storage, contract,
                                                       monkeypatch):
    """42.5 — Attempt 1 FAILED, Attempt 2 COMPLETED must both remain visible."""
    # The first attempt must fail for a stated reason, not because a blank page
    # happens to OCR to nothing on this machine.
    monkeypatch.setattr(parsing, "ocr_available", lambda: False)
    result = ingest_document(
        db, storage, contract_id=contract.id, uploaded_by=contract._owner.id,
        data=build_image_only_pdf(), filename="scan.pdf", declared_mime=PDF_MIME)
    first_run = result.processing_run
    assert first_run.status is E.ProcessingRunStatus.FAILED

    second_run = process_document_version(
        db, storage, result.document_version,
        run_type=E.ProcessingRunType.REPROCESS)

    runs = db.query(M.DocumentProcessingRun).filter_by(
        document_version_id=result.document_version.id).all()
    assert len(runs) == 2
    assert second_run.id != first_run.id
    assert first_run.status is E.ProcessingRunStatus.FAILED   # history intact


def test_extraction_status_is_separate_from_review_lifecycle(db, storage, contract):
    """34.15 / Step 30 r13 — a document-level failure is not a Finding, and
    ANALYSIS_FAILED is not UNABLE_TO_EVALUATE."""
    result = ingest_document(
        db, storage, contract_id=contract.id, uploaded_by=contract._owner.id,
        data=build_image_only_pdf(), filename="scan.pdf", declared_mime=PDF_MIME)
    dv = result.document_version
    assert isinstance(dv.extraction_status, E.ExtractionStatus)
    # The document carries no review status and no finding classification.
    assert not hasattr(dv, "status")
    assert not hasattr(dv, "classification")


def test_ocr_derived_content_would_be_labelled(db):
    """34.8 — OCR-derived content is explicitly identified.

    The toolchain is absent here, so this asserts the labelling contract rather
    than running OCR: OCR segments carry source_type OCR, which is a distinct
    enum member from NATIVE_TEXT.
    """
    from legalmind.ingestion.parsing import Segment
    seg = Segment(content="x", original_content="x",
                  source_type=E.EvidenceSourceType.OCR)
    assert seg.source_type is not E.EvidenceSourceType.NATIVE_TEXT
    assert E.EvidenceSourceType.OCR.value == "OCR"


def test_normalization_never_alters_numbers_or_words(db):
    """45C.18 — normalizing an OCR error is permitted only when deterministic;
    this layer cannot establish that, so it only touches whitespace."""
    raw = "Liability shall not exceed 6 m0nths of fees"
    assert parsing.normalize_text(raw) == raw     # '6 m0nths' left untouched


# --------------------------------------------------------------------------
# Structural segmentation — 2026-09-05.
#
# The defect these pin, measured on the owner's own file: the SAME MSA gave 356
# segments as .docx and 32 as .docx.pdf. The PDF converter emits one newline per
# visual line and never a blank line, so a 28-page contract arrived as 28 blocks
# of 3,000+ characters — and since only a block's first line was read for a
# clause number, §10.2 appeared in the outline while §10 and §10.1, plainly
# present in the text, did not.
# --------------------------------------------------------------------------
_NO_BLANK_LINES = (
    "13. LIMITATION ON DAMAGES\n"
    "13.1 The total liability of Leapswitch shall not exceed the fees paid.\n"
    "13.2 In no event shall Leapswitch be liable for indirect damages.\n"
    "14. CONFIDENTIALITY\n"
    "14.1 Each Party shall keep the other's information confidential.\n"
)


def test_a_page_without_blank_lines_is_still_split_into_clauses():
    """The GRP case. One block in, one segment per clause out."""
    segments = parsing.segment_paragraphs(
        _NO_BLANK_LINES, page_number=1,
        source_type=E.EvidenceSourceType.NATIVE_TEXT)

    assert [s.section_number for s in segments] == ["13", "13.1", "13.2", "14", "14.1"]
    # And the clause that used to vanish is now its own row with its own text.
    body = next(s for s in segments if s.section_number == "13.1")
    assert "shall not exceed the fees paid" in body.content


def test_blank_line_documents_segment_exactly_as_before():
    """The other half of the guard: no regression on files that already worked."""
    text = "1. TERM\n\nThe term is twelve months.\n\n2. FEES\n\nFees are payable monthly."
    numbers = [s.section_number for s in parsing.segment_paragraphs(
        text, page_number=1, source_type=E.EvidenceSourceType.NATIVE_TEXT)]
    assert numbers == ["1", None, "2", None]


def test_a_number_inside_a_sentence_is_not_a_clause_boundary():
    """`detect_clause_number` anchors at the start of a line, so prose that
    merely CONTAINS a decimal is one segment, not three."""
    text = ("5.1 The cap is limited to 13.2 million rupees in aggregate\n"
            "and no more than 4.5 million per claim under this Agreement.\n")
    segments = parsing.segment_paragraphs(
        text, page_number=1, source_type=E.EvidenceSourceType.NATIVE_TEXT)
    assert len(segments) == 1
    assert segments[0].section_number == "5.1"


def test_offsets_still_resolve_back_to_the_source_text():
    """34.13 — every segment must be locatable in the document it came from.
    Splitting inside a block is where that would quietly break."""
    for segment in parsing.segment_paragraphs(
            _NO_BLANK_LINES, page_number=1,
            source_type=E.EvidenceSourceType.NATIVE_TEXT):
        assert segment.start_offset is not None and segment.end_offset is not None
        window = _NO_BLANK_LINES[segment.start_offset:segment.end_offset]
        assert parsing.normalize_text(window) == segment.content


def test_segmentation_is_deterministic():
    """ENG-11. Same text twice, byte-identical segments."""
    kwargs = {"page_number": 1, "source_type": E.EvidenceSourceType.NATIVE_TEXT}
    first = parsing.segment_paragraphs(_NO_BLANK_LINES, **kwargs)
    second = parsing.segment_paragraphs(_NO_BLANK_LINES, **kwargs)
    assert [(s.content, s.start_offset, s.end_offset) for s in first] == \
           [(s.content, s.start_offset, s.end_offset) for s in second]


def test_a_heading_is_marked_and_a_clause_body_is_not():
    """The marker rides in the metadata dict the Segment already had, which
    `ingest` already merges into `evidence_metadata` — no column, no plumbing."""
    segments = {s.section_number: s for s in parsing.segment_paragraphs(
        _NO_BLANK_LINES, page_number=1,
        source_type=E.EvidenceSourceType.NATIVE_TEXT)}

    assert segments["13"].metadata.get("heading") is True
    assert segments["14"].metadata.get("heading") is True
    # Body text that happens to carry a number is NOT a heading — putting it in
    # an outline is exactly what made the Clauses panel unreadable.
    assert "heading" not in segments["13.1"].metadata
    assert "heading" not in segments["13.2"].metadata


# --------------------------------------------------------------------------
# Unnumbered headings and bare clause numbers — 2026-09-05.
#
# Measured on the supplied corpus: the CloudPe terms of service and privacy
# policy carry NO clause numbering at all, but they are not unstructured — they
# are organised by prose headings. Recognising only numbered headings meant the
# whole document arrived as one block per page and the structural gate refused
# it. The structure was there; we could not see it.
# --------------------------------------------------------------------------
def test_an_unnumbered_heading_starts_a_section_and_names_it():
    text = ("Cancellations\n"
            "Cancellation requests need to be submitted via our Client Area and "
            "cannot be accepted by support ticket.\n"
            "Late Fees\n"
            "Invoices overdue for over 5 days will be charged a late fee of up to "
            "5% per month on the outstanding amount.\n")
    segments = parsing.segment_paragraphs(
        text, page_number=1, source_type=E.EvidenceSourceType.NATIVE_TEXT)

    assert [s.section_title for s in segments] == ["Cancellations", "Late Fees"]
    assert all(s.metadata.get("heading") for s in segments)
    assert all(s.section_number is None for s in segments)   # nothing invented
    # The heading keeps the prose it introduces, so the outline entry points at
    # the text it labels rather than at an empty label above it.
    assert "Client Area" in segments[0].content


def test_a_navigation_list_is_not_a_run_of_headings():
    """The page footer of a printed web page: every line is short and
    title-like. A heading is followed by the prose it introduces; a menu item is
    followed by another menu item."""
    text = "VPS\nKubernetes\nStorage\nNetworking\nGPU Cloud\nCareers\nBlog\n"
    segments = parsing.segment_paragraphs(
        text, page_number=4, source_type=E.EvidenceSourceType.NATIVE_TEXT)

    assert len(segments) == 1
    assert not segments[0].metadata.get("heading")


def test_a_bare_clause_number_on_its_own_line_is_a_boundary():
    """PDF layouts routinely put the number on one line and its text on the
    next. Four clauses of the owner's own MSA were lost to this."""
    text = ("17. DATA PRIVACY\n"
            "17.1\n"
            "The Customer acknowledges that Leapswitch may disclose information.\n"
            "17.2\n"
            "Leapswitch shall protect the confidentiality of Personal Data.\n")
    numbers = [s.section_number for s in parsing.segment_paragraphs(
        text, page_number=1, source_type=E.EvidenceSourceType.NATIVE_TEXT)]
    assert numbers == ["17", "17.1", "17.2"]


def test_a_bare_year_or_page_number_is_still_not_a_clause():
    """The other half. `1999.` and `12` carry no interior dot, which is exactly
    what the bare-number pattern requires — so neither is ever a clause."""
    assert parsing.detect_clause_number("1999.") == (None, None)
    assert parsing.detect_clause_number("12") == (None, None)
    assert parsing.detect_clause_number("17.") == (None, None)
    assert parsing.detect_clause_number("17.1") == ("17.1", None)


def test_a_broken_sentence_is_not_promoted_to_a_heading():
    """The false positive found in validation: a PDF broke this line mid-
    sentence, so the truncated title lost its full stop and read as a label.
    Word count and the interior full stop both catch it now."""
    text = ("3.1 Customers shall raise purchase orders on Leapswitch for the "
            "provision of Services. Subject to Clause\n")
    segment = parsing.segment_paragraphs(
        text, page_number=3, source_type=E.EvidenceSourceType.NATIVE_TEXT)[0]

    assert segment.section_number == "3.1"
    assert not segment.metadata.get("heading")


# =====================================================================
# P-8 — one processing run IS the document (2026-09-06)
# =====================================================================
def test_latest_completed_run_is_the_one_every_reader_uses(db):
    """FAILED and STARTED attempts are history (42.5), never content; of two
    COMPLETED runs the later `started_at` wins; none yet → None, so a version
    still processing shows nothing rather than a stale reading."""
    from datetime import UTC, datetime, timedelta

    from legalmind.db import models as M
    from legalmind.db.lookup import latest_completed_run_id
    from legalmind.domain import enums as E
    from tests.conftest import make_user

    owner = make_user(db)
    contract = M.Contract(owner_id=owner.id, name="ACME MSA",
                          status=E.ContractStatus.ACTIVE)
    db.add(contract); db.flush()
    version = M.DocumentVersion(
        contract_id=contract.id, version_number=1, original_filename="a.pdf",
        mime_type="application/pdf", file_size_bytes=1, file_hash="h",
        storage_key="k", processing_status=E.ProcessingStatus.COMPLETED,
        uploaded_by=owner.id)
    db.add(version); db.flush()
    assert latest_completed_run_id(db, version.id) is None

    t0 = datetime(2026, 9, 6, 12, 0, tzinfo=UTC)

    def run(status, minutes, run_type=E.ProcessingRunType.PARSE):
        r = M.DocumentProcessingRun(
            document_version_id=version.id, run_type=run_type, status=status,
            processor_version="t", started_at=t0 + timedelta(minutes=minutes))
        db.add(r); db.flush()
        return r

    first = run(E.ProcessingRunStatus.COMPLETED, 0)
    assert latest_completed_run_id(db, version.id) == first.id
    run(E.ProcessingRunStatus.FAILED, 1)        # a failed retry changes nothing
    run(E.ProcessingRunStatus.STARTED, 2)       # nor one still in flight
    assert latest_completed_run_id(db, version.id) == first.id
    second = run(E.ProcessingRunStatus.COMPLETED, 3, E.ProcessingRunType.REPROCESS)
    assert latest_completed_run_id(db, version.id) == second.id


# =====================================================================
# 44.4 — annexures/schedules where detectable (2026-09-06)
# =====================================================================
def test_annexure_titles_are_detected_where_the_document_declares_them():
    """Detectable means the document says so, in a title line of its own; the
    label is the document's text verbatim (34.12). Prose that mentions a
    schedule is not one, and a bare "Schedule" with no label is not claimed.
    Segmentation itself is untouched: the title becomes a marked heading, the
    boundaries and content are what they were."""
    from legalmind.domain.enums import EvidenceSourceType
    from legalmind.ingestion.parsing import annexure_title, segment_paragraphs

    for line in ("Annexure-1", "Annexure-3A ", "Appendix-3B", "Schedule 2 – Fees",  # noqa: RUF001 - en dash is the point
                 "Exhibit A", "ANNEX II"):
        assert annexure_title(line) == line.strip(), line
    for line in ("Schedule", "Annexure 1 forms part of this Agreement.",
                 "The Schedule 2 fees apply.", "13. LIMITATION ON DAMAGES"):
        assert annexure_title(line) is None, line

    text = ("Annexure-1\n\nScope of Services\n\n"
            "The Provider shall deliver the services described below to the Customer.")
    segments = segment_paragraphs(text, page_number=18,
                                  source_type=EvidenceSourceType.NATIVE_TEXT)
    first = segments[0]
    assert first.content == "Annexure-1"
    assert first.metadata == {"heading": True, "annexure": "Annexure-1"}
    assert first.section_title == "Annexure-1" and first.section_number is None
    assert all("annexure" not in s.metadata for s in segments[1:])


def test_docx_paragraphs_carry_the_same_structure_markers_as_pdf_text():
    """Found by the post-deploy smoke test (2026-09-06): `parse_docx` built its
    Segments directly and skipped every marker `segment_paragraphs` applies, so a
    Word upload had NO heading and NO annexure markers — only the outline's
    fallback — while the same text as a PDF had both. One shared helper now
    decides the markers for both paths. Boundaries and content are unchanged:
    one paragraph is still one segment."""
    import io

    import docx

    d = docx.Document()
    for text in ("1. Definitions",
                 "Capitalized terms have the meanings given below in this document.",
                 "13. LIMITATION ON DAMAGES",
                 "13.1 The total liability of either party shall not exceed the fees paid.",
                 "Annexure-1",
                 "Scope of Services",
                 "The Provider shall deliver the services described in this annexure to the Customer."):
        d.add_paragraph(text)
    buf = io.BytesIO(); d.save(buf)
    from legalmind.ingestion import parsing
    segments = parsing.parse(
        buf.getvalue(),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document").segments
    by_first = {s.content.splitlines()[0]: s for s in segments}

    assert len(segments) == 7                                  # one paragraph, one segment
    assert by_first["13. LIMITATION ON DAMAGES"].metadata.get("heading") is True
    assert "heading" not in by_first["13.1 The total liability of either party shall not exceed the fees paid."].metadata
    annex = by_first["Annexure-1"]
    assert annex.metadata.get("heading") is True and annex.metadata.get("annexure") == "Annexure-1"
    assert annex.section_title == "Annexure-1"
    # An unnumbered prose heading followed by its prose — the same rule as PDF text,
    # with "following" read from the next paragraph.
    assert by_first["Scope of Services"].metadata.get("heading") is True
    # The DOCX-specific style key is kept alongside the shared markers.
    assert "style" in annex.metadata
