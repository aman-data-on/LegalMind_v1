"""Document ingestion service — locked Step 34.

Pipeline:

    validate (untrusted input)      34.16
        -> store original           34.5, 34.18  write-once
        -> DocumentVersion          42.4         immutable, fingerprinted
        -> ProcessingRun            42.5         attempt history preserved
        -> parse                    34.6 - 34.14
        -> DocumentEvidence         42.6         source locations retained

Two locked rules shape the error handling:

* **34.9** extraction failures never invent text or legal conclusions.
* **34.15** document extraction status is separate from Review lifecycle status
  (Step 30 also distinguishes `ANALYSIS_FAILED` from `UNABLE_TO_EVALUATE`).

A parse failure therefore records a FAILED processing run and a FAILED
extraction status — it does not raise into the caller's face as an unexpected
error, and it does not fabricate evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DBSession

from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.ingestion import parsing
from legalmind.ingestion.storage import StorageBackend, fingerprint
from legalmind.ingestion.validation import validate_upload

# v2 (2026-09-02): DOCX page numbers from the document's own pagination record
# (rendered/explicit break markers — parsing._docx_paragraph_pages). Runs are
# attributable to the processor that made them (42.5), so behavior changes bump
# this; v1 runs left every DOCX page_number null.
# v3 (2026-09-03): OCR became its own deferrable processing run (42.5's
# ProcessingRunType.OCR) and pages OCR in parallel. Output for a given document
# is unchanged (measured byte-identical on the real corpus document); the run
# structure is what changed, and the processor version records that honestly.
PROCESSOR_VERSION = "legalmind-ingest-v3"


@dataclass(frozen=True)
class IngestResult:
    document_version: M.DocumentVersion
    processing_run: M.DocumentProcessingRun
    evidence_count: int
    duplicate_of: UUID | None
    diagnostics: list[str]


def _now() -> datetime:
    return datetime.now(UTC)


def find_duplicate(db: DBSession, contract_id: UUID,
                   file_hash: str) -> M.DocumentVersion | None:
    """Locked 34.5 — exact duplicate files should be detectable.

    Scoped to the contract: locked 42.4 states file_hash must NOT be globally
    unique, because the same source file may legitimately appear in several
    contracts. Detecting a duplicate is reported to the caller; it does not
    silently suppress the upload, because whether a re-upload is a new
    contractual version is a business decision (Step 33.9).
    """
    return db.execute(
        select(M.DocumentVersion).where(
            M.DocumentVersion.contract_id == contract_id,
            M.DocumentVersion.file_hash == file_hash,
        ).order_by(M.DocumentVersion.version_number)
    ).scalars().first()


def _next_version_number(db: DBSession, contract_id: UUID) -> int:
    """Locked 42.4 UNIQUE(contract_id, version_number); Step 33.6 —
    system-controlled sequential numbering that users cannot rewrite."""
    current = db.execute(
        select(func.max(M.DocumentVersion.version_number))
        .where(M.DocumentVersion.contract_id == contract_id)
    ).scalar()
    return (current or 0) + 1


def ingest_document(
    db: DBSession,
    storage: StorageBackend,
    *,
    contract_id: UUID,
    uploaded_by: UUID,
    data: bytes,
    filename: str,
    declared_mime: str,
    defer_ocr: bool = False,
) -> IngestResult:
    """Ingest one uploaded document. Raises only on validation rejection.

    With ``defer_ocr`` (the upload endpoint's mode since 2026-09-03), a document
    that needs OCR comes back with ``processing_status=PROCESSING``, no evidence,
    and no extraction verdict — the caller is expected to dispatch the OCR pass
    (``worker.dispatch.dispatch_ocr``), which finishes the job as its own
    ProcessingRun. Everything else — a legible native-text document, a failed
    parse, OCR toolchain absent — concludes inline exactly as before.
    """
    validated = validate_upload(data, filename, declared_mime)   # 34.16
    digest = fingerprint(validated.data)                         # 34.4
    duplicate = find_duplicate(db, contract_id, digest)          # 34.5

    # The original is stored before anything parses it, and is never mutated
    # afterwards (34.5, 34.18).
    storage_key = storage.put(validated.data, suggested_name=validated.filename)

    version = M.DocumentVersion(
        contract_id=contract_id,
        version_number=_next_version_number(db, contract_id),
        original_filename=validated.filename,
        mime_type=validated.mime_type,
        file_size_bytes=validated.size_bytes,
        file_hash=digest,
        storage_key=storage_key,
        processing_status=E.ProcessingStatus.PENDING,
        uploaded_by=uploaded_by,
        doc_metadata={"duplicate_of": str(duplicate.id)} if duplicate else None,
    )
    db.add(version)
    db.flush()

    run = process_document_version(db, storage, version, defer_ocr=defer_ocr)

    return IngestResult(
        document_version=version,
        processing_run=run,
        evidence_count=db.execute(
            select(func.count(M.DocumentEvidence.id))
            .where(M.DocumentEvidence.processing_run_id == run.id)
        ).scalar_one(),
        duplicate_of=duplicate.id if duplicate else None,
        diagnostics=list((run.run_metadata or {}).get("diagnostics", [])),
    )


def process_document_version(
    db: DBSession,
    storage: StorageBackend,
    version: M.DocumentVersion,
    *,
    run_type: E.ProcessingRunType = E.ProcessingRunType.PARSE,
    defer_ocr: bool = False,
    run: M.DocumentProcessingRun | None = None,
) -> M.DocumentProcessingRun:
    """Parse a stored document version into evidence.

    Locked 42.5 preserves attempt history: a retry creates a NEW run rather than
    overwriting the previous one, so ``Attempt 1 -> FAILED, Attempt 2 ->
    COMPLETED`` remains visible.

    ``run`` (the background-OCR claim pattern, 2026-09-03): the caller may hand
    in a STARTED run it already created — and, crucially, already COMMITTED — so
    that an attempt which dies with its process still left a visible record
    (42.5's history includes crashed attempts, which is what makes them
    countable). When omitted, the run is created here exactly as before.
    """
    if run is None:
        run = M.DocumentProcessingRun(
            document_version_id=version.id,
            run_type=run_type,
            status=E.ProcessingRunStatus.STARTED,
            processor_version=PROCESSOR_VERSION,
            started_at=_now(),
        )
        db.add(run)
        db.flush()

    version.processing_status = E.ProcessingStatus.PROCESSING
    db.flush()

    try:
        result = parsing.parse(storage.get(version.storage_key), version.mime_type,
                               defer_ocr=defer_ocr)
    except parsing.ParseError as exc:
        # 34.9 / 34.4 — a document we cannot read yields no text, not invented
        # text. The affected Finding may later become UNABLE_TO_EVALUATE (34.17).
        run.status = E.ProcessingRunStatus.FAILED
        run.completed_at = _now()
        run.error_code = "EXTRACTION_FAILED"
        run.error_message = str(exc)
        run.run_metadata = {"diagnostics": [str(exc)]}
        version.processing_status = E.ProcessingStatus.FAILED
        version.extraction_status = E.ExtractionStatus.FAILED
        db.flush()
        return run

    if result.needs_ocr:
        # The parse ran and concluded that OCR is required. That conclusion is
        # this run's honest, complete outcome; the extraction verdict itself
        # belongs to the OCR run the caller will dispatch (42.5 — a new attempt
        # is a NEW run). The version stays PROCESSING — true, and the state the
        # UI already renders as "still being processed" — and extraction_status
        # stays NULL, because no verdict exists yet. No evidence rows are
        # written: the illegible/absent native text must never look like content.
        run.status = E.ProcessingRunStatus.COMPLETED
        run.completed_at = _now()
        run.run_metadata = {
            "diagnostics": result.diagnostics,
            "pages_total": result.pages_total,
            "ocr_required": True,
        }
        db.flush()
        return run

    for segment in result.segments:
        db.add(M.DocumentEvidence(
            document_version_id=version.id,
            processing_run_id=run.id,
            page_number=segment.page_number,
            section_number=segment.section_number,
            section_title=segment.section_title,
            content=segment.content,
            source_type=segment.source_type,
            start_offset=segment.start_offset,
            end_offset=segment.end_offset,
            # 34.14 — the original extracted text is preserved alongside the
            # normalized text.
            evidence_metadata={"original_content": segment.original_content,
                               **segment.metadata},
        ))

    run.status = (E.ProcessingRunStatus.COMPLETED
                  if result.status is not E.ExtractionStatus.FAILED
                  else E.ProcessingRunStatus.FAILED)
    run.completed_at = _now()
    run.run_metadata = {
        "diagnostics": result.diagnostics,
        "pages_total": result.pages_total,
        "pages_extracted": result.pages_extracted,
        "pages_failed": result.pages_failed,
        # Where page numbers came from (None = no page model in the document):
        # physical PDF pages, or the DOCX file's own pagination record.
        "pagination_source": result.pagination_source,
    }
    if result.status is E.ExtractionStatus.FAILED:
        run.error_code = "EXTRACTION_FAILED"
        run.error_message = "No usable text could be extracted."

    # 34.15 — extraction status is a document concern, separate from Review
    # lifecycle status.
    version.extraction_status = result.status
    version.processing_status = (
        E.ProcessingStatus.COMPLETED
        if result.status is not E.ExtractionStatus.FAILED
        else E.ProcessingStatus.FAILED
    )
    db.flush()
    return run


def run_ocr_pass(
    db: DBSession,
    storage: StorageBackend,
    version: M.DocumentVersion,
    *,
    run: M.DocumentProcessingRun | None = None,
) -> M.DocumentProcessingRun:
    """The deferred OCR pass — the second half of an upload whose parse said
    ``ocr_required``.

    A thin, named wrapper: it is ``process_document_version`` with
    ``run_type=OCR`` (locked 42.5 gives OCR its own run type precisely so the
    attempt history reads ``PARSE -> ocr_required, OCR -> COMPLETED/FAILED``)
    and OCR running inline — this IS the OCR run, there is nothing further to
    defer to. It sets the version's final processing and extraction statuses
    exactly as the single-run path always has.
    """
    return process_document_version(db, storage, version,
                                    run_type=E.ProcessingRunType.OCR, run=run)
