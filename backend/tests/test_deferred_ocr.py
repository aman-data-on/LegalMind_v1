"""The deferred OCR run — the ~63s-upload fix (2026-09-03).

Measured on the real 30-page document that motivated this: the upload request
spent 63.4s inside tesseract and under half a second in everything else
combined. The fix is structural, not a faster OCR: the upload runs only the
fast native parse plus the legibility verdict, and when OCR is required it is
dispatched as its own background ProcessingRun — the run type locked 42.5
already reserves for exactly this (``ProcessingRunType.OCR``).

What must stay true, and is pinned here:

* deferral happens ONLY when OCR is actually required AND the toolchain exists
  — a legible document concludes inline exactly as before, and a machine
  without OCR fails closed NOW, not later;
* the in-between state is honest vocabulary: ``processing_status=PROCESSING``,
  ``extraction_status`` NULL (no verdict exists yet), zero evidence rows — the
  illegible native text must never look like content;
* the OCR run finishes the job with the same statuses the single-run path
  always produced, and the attempt history reads PARSE → OCR (42.5);
* analysis over a still-processing version is refused (34.9's spirit: zero
  evidence must not mint MISSING findings against text still being recovered).
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from legalmind.analysis.service import AnalysisNotPermitted, assert_analysable
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.ingestion import parsing
from legalmind.ingestion.service import ingest_document, run_ocr_pass
from legalmind.ingestion.storage import LocalFilesystemStorage
from legalmind.ingestion.validation import PDF_MIME
from tests.conftest import make_user
from tests.test_analysis import LEGAL_RULE, MAPPING, STANDARD, Builder
from tests.test_extraction_legibility import LEGAL_PROSE, build_pdf, mangle

READABLE_PAGE = (
    "1. Limitation of Liability. "
    "Liability shall not exceed 6 months of fees paid. "
) + LEGAL_PROSE[:1600]


@pytest.fixture
def store(tmp_path):
    return LocalFilesystemStorage(tmp_path / "objects")


def _ingest(db, store, pdf_bytes, *, defer_ocr):
    owner = make_user(db)
    contract = M.Contract(owner_id=owner.id, name="Deferred OCR",
                          contract_type="MSA", status=E.ContractStatus.ACTIVE)
    db.add(contract)
    db.flush()
    return ingest_document(db, store, contract_id=contract.id,
                           uploaded_by=owner.id, data=pdf_bytes,
                           filename="doc.pdf", declared_mime=PDF_MIME,
                           defer_ocr=defer_ocr)


# --------------------------------------------------------------------------
# When deferral happens, and when it must not
# --------------------------------------------------------------------------
def test_an_illegible_pdf_defers_and_stays_honestly_processing(db, store, monkeypatch):
    monkeypatch.setattr(parsing, "ocr_available", lambda: True)

    result = _ingest(db, store, build_pdf([mangle(READABLE_PAGE)]), defer_ocr=True)
    version = result.document_version

    # The in-between vocabulary: PROCESSING is true (work continues), and no
    # extraction verdict exists yet, so none is asserted (34.15's axis stays NULL).
    assert version.processing_status is E.ProcessingStatus.PROCESSING
    assert version.extraction_status is None
    assert result.evidence_count == 0

    # The PARSE run completed — its honest outcome is "OCR required".
    run = result.processing_run
    assert run.run_type is E.ProcessingRunType.PARSE
    assert run.status is E.ProcessingRunStatus.COMPLETED
    assert run.run_metadata["ocr_required"] is True
    assert any("deferred" in d for d in result.diagnostics)


def test_a_legible_pdf_concludes_inline_even_when_deferral_is_allowed(db, store):
    result = _ingest(db, store, build_pdf([READABLE_PAGE]), defer_ocr=True)
    version = result.document_version

    assert version.processing_status is E.ProcessingStatus.COMPLETED
    assert version.extraction_status is E.ExtractionStatus.COMPLETE
    assert result.evidence_count > 0


def test_without_the_toolchain_deferral_never_happens_and_failure_is_now(db, store, monkeypatch):
    """There is nothing to defer TO. Fail closed immediately, exactly as before —
    a PROCESSING that no background run will ever resolve would be a lie."""
    monkeypatch.setattr(parsing, "ocr_available", lambda: False)

    result = _ingest(db, store, build_pdf([mangle(READABLE_PAGE)]), defer_ocr=True)
    version = result.document_version

    assert version.processing_status is E.ProcessingStatus.FAILED
    assert version.extraction_status is E.ExtractionStatus.FAILED
    assert result.evidence_count == 0


def test_no_evidence_row_exists_while_ocr_is_pending(db, store, monkeypatch):
    """The mojibake must not be persisted in the gap either — the deferred state
    is `nothing extracted yet`, never `the native text meanwhile`."""
    monkeypatch.setattr(parsing, "ocr_available", lambda: True)

    result = _ingest(db, store, build_pdf([mangle(READABLE_PAGE)]), defer_ocr=True)
    rows = db.execute(
        select(M.DocumentEvidence)
        .where(M.DocumentEvidence.document_version_id == result.document_version.id)
    ).scalars().all()
    assert rows == []


# --------------------------------------------------------------------------
# The OCR run completes the document
# --------------------------------------------------------------------------
def test_the_ocr_run_finishes_the_job_and_the_history_reads_parse_then_ocr(
        db, store, monkeypatch):
    """PARSE → ocr_required, OCR → COMPLETED — 42.5's attempt history, with the
    final statuses identical to what the old single-run path produced."""
    monkeypatch.setattr(parsing, "ocr_available", lambda: True)
    # The OCR outcome itself is simulated (the real-toolchain path is proven by
    # test_the_real_toolchain_recovers_an_illegible_document); what is under
    # test here is the run structure and the statuses it leaves behind.
    monkeypatch.setattr(parsing, "_ocr_pages_parallel",
                        lambda data, n: [(i, READABLE_PAGE) for i in range(1, n + 1)])

    result = _ingest(db, store, build_pdf([mangle(READABLE_PAGE)]), defer_ocr=True)
    version = result.document_version
    assert version.processing_status is E.ProcessingStatus.PROCESSING

    ocr_run = run_ocr_pass(db, store, version)

    assert ocr_run.run_type is E.ProcessingRunType.OCR
    assert ocr_run.status is E.ProcessingRunStatus.COMPLETED
    assert version.processing_status is E.ProcessingStatus.COMPLETED
    assert version.extraction_status is E.ExtractionStatus.COMPLETE

    rows = db.execute(
        select(M.DocumentEvidence)
        .where(M.DocumentEvidence.document_version_id == version.id)
    ).scalars().all()
    assert rows and all(r.source_type is E.EvidenceSourceType.OCR for r in rows)

    runs = db.execute(
        select(M.DocumentProcessingRun)
        .where(M.DocumentProcessingRun.document_version_id == version.id)
        .order_by(M.DocumentProcessingRun.started_at)
    ).scalars().all()
    assert [r.run_type for r in runs] == [E.ProcessingRunType.PARSE,
                                          E.ProcessingRunType.OCR]


def test_an_ocr_run_that_recovers_nothing_fails_closed(db, store, monkeypatch):
    """OCR that produces illegible text is discarded, and the version ends
    FAILED/FAILED — the deferred path must not weaken 34.9's refusal."""
    monkeypatch.setattr(parsing, "ocr_available", lambda: True)
    monkeypatch.setattr(parsing, "_ocr_pages_parallel",
                        lambda data, n: [(i, mangle(READABLE_PAGE))
                                         for i in range(1, n + 1)])

    result = _ingest(db, store, build_pdf([mangle(READABLE_PAGE)]), defer_ocr=True)
    version = result.document_version
    run_ocr_pass(db, store, version)

    assert version.processing_status is E.ProcessingStatus.FAILED
    assert version.extraction_status is E.ExtractionStatus.FAILED
    rows = db.execute(
        select(M.DocumentEvidence)
        .where(M.DocumentEvidence.document_version_id == version.id)
    ).scalars().all()
    assert rows == []


# --------------------------------------------------------------------------
# Analysis is refused while processing
# --------------------------------------------------------------------------
def test_analysis_is_refused_while_the_document_is_still_processing(
        db, tmp_path, monkeypatch):
    monkeypatch.setattr(parsing, "ocr_available", lambda: True)
    storage = LocalFilesystemStorage(tmp_path / "objects")
    build = Builder(db, storage, make_user(db))
    build.requirement("LIABILITY-001", E.EvaluatorType.NUMERIC_COMPARISON,
                      mapping=MAPPING, standard=STANDARD, legal_rule=LEGAL_RULE)

    contract = M.Contract(owner_id=build.owner.id, name="Still processing",
                          contract_type="MSA", status=E.ContractStatus.ACTIVE)
    db.add(contract)
    db.flush()
    result = ingest_document(db, storage, contract_id=contract.id,
                             uploaded_by=build.owner.id,
                             data=build_pdf([mangle(READABLE_PAGE)]),
                             filename="doc.pdf", declared_mime=PDF_MIME,
                             defer_ocr=True)
    review = M.Review(contract_id=contract.id,
                      document_version_id=result.document_version.id,
                      configuration_snapshot_id=build.snapshot.id,
                      status=E.ReviewStatus.DRAFT, created_by=build.owner.id)
    db.add(review)
    db.flush()

    with pytest.raises(AnalysisNotPermitted, match="still being processed"):
        assert_analysable(db, review)


# --------------------------------------------------------------------------
# The upload endpoint dispatches, and reports the honest in-between state
# --------------------------------------------------------------------------
def test_the_upload_endpoint_defers_and_dispatches_the_ocr_run(
        api, db, seeded, user, monkeypatch):
    from legalmind.api.routers import contracts as contracts_router
    from tests.conftest import grant_role, sign_in

    monkeypatch.setattr(parsing, "ocr_available", lambda: True)
    dispatched: list[str] = []
    monkeypatch.setattr(contracts_router, "dispatch_ocr",
                        lambda version_id, request_id=None:
                        dispatched.append(str(version_id)) or "THREAD")

    grant_role(db, user, "USER")
    sign_in(api, db, user)
    contract_id = api.post("/api/v1/contracts",
                           json={"name": "Scanned upload", "contract_type": "MSA"}
                           ).json()["data"]["id"]

    uploaded = api.post(f"/api/v1/contracts/{contract_id}/document-versions",
                        content=build_pdf([mangle(READABLE_PAGE)]),
                        headers={"content-type": PDF_MIME,
                                 "x-filename": "scan.pdf"})
    assert uploaded.status_code == 201, uploaded.text

    version = uploaded.json()["data"]["document_version"]
    assert version["processing_status"] == "PROCESSING"
    assert version["extraction_status"] is None
    assert uploaded.json()["data"]["evidence_count"] == 0
    assert dispatched == [version["id"]]


# --------------------------------------------------------------------------
# Durability — the process is disposable, the database is the ledger
# --------------------------------------------------------------------------
def test_a_claim_run_is_finalised_not_duplicated(db, store, monkeypatch):
    """The claim pattern: the thread commits a STARTED run before parsing and
    hands it to `run_ocr_pass`, which must finalise THAT run — a second row
    would double the attempt history and miscount toward the cap."""
    from legalmind.ingestion.service import PROCESSOR_VERSION

    monkeypatch.setattr(parsing, "ocr_available", lambda: True)
    monkeypatch.setattr(parsing, "_ocr_pages_parallel",
                        lambda data, n: [(i, READABLE_PAGE) for i in range(1, n + 1)])
    result = _ingest(db, store, build_pdf([mangle(READABLE_PAGE)]), defer_ocr=True)
    version = result.document_version

    claim = M.DocumentProcessingRun(
        document_version_id=version.id,
        run_type=E.ProcessingRunType.OCR,
        status=E.ProcessingRunStatus.STARTED,
        processor_version=PROCESSOR_VERSION,
        started_at=result.processing_run.started_at,
    )
    db.add(claim)
    db.flush()

    finished = run_ocr_pass(db, store, version, run=claim)

    assert finished.id == claim.id
    assert claim.status is E.ProcessingRunStatus.COMPLETED
    runs = db.execute(
        select(M.DocumentProcessingRun)
        .where(M.DocumentProcessingRun.document_version_id == version.id)
    ).scalars().all()
    # Exactly two: the PARSE that said ocr_required, and the finalised claim.
    assert sorted(r.run_type.value for r in runs) == ["OCR", "PARSE"]


def test_attempt_state_reads_the_committed_ledger(db, store, monkeypatch):
    """`_ocr_attempt_state` is the whole crash-recovery decision: run while
    under the cap, abandon at it, and treat any concluded version as done."""
    from legalmind.ingestion.service import PROCESSOR_VERSION, _now
    from legalmind.worker.dispatch import OCR_MAX_ATTEMPTS, _ocr_attempt_state

    monkeypatch.setattr(parsing, "ocr_available", lambda: True)
    result = _ingest(db, store, build_pdf([mangle(READABLE_PAGE)]), defer_ocr=True)
    version = result.document_version

    assert _ocr_attempt_state(db, version.id) == "run"

    # Crashed attempts are STARTED runs that never finished — committed before
    # the risky work, which is exactly what makes them countable here.
    for _ in range(OCR_MAX_ATTEMPTS):
        db.add(M.DocumentProcessingRun(
            document_version_id=version.id,
            run_type=E.ProcessingRunType.OCR,
            status=E.ProcessingRunStatus.STARTED,
            processor_version=PROCESSOR_VERSION,
            started_at=_now(),
        ))
    db.flush()
    assert _ocr_attempt_state(db, version.id) == "abandon"

    version.processing_status = E.ProcessingStatus.COMPLETED
    db.flush()
    assert _ocr_attempt_state(db, version.id) == "concluded"

    from uuid import uuid4
    assert _ocr_attempt_state(db, uuid4()) == "concluded"


def test_abandonment_is_a_deterministic_terminal_state(db, store, monkeypatch):
    """A document that keeps killing its process converges to FAILED — with a
    committed FAILED run saying why — never to an infinite restart loop and
    never to an eternal PROCESSING."""
    from legalmind.worker.dispatch import _abandon_ocr

    monkeypatch.setattr(parsing, "ocr_available", lambda: True)
    result = _ingest(db, store, build_pdf([mangle(READABLE_PAGE)]), defer_ocr=True)
    version = result.document_version

    _abandon_ocr(db, version.id)

    assert version.processing_status is E.ProcessingStatus.FAILED
    assert version.extraction_status is E.ExtractionStatus.FAILED
    last = db.execute(
        select(M.DocumentProcessingRun)
        .where(M.DocumentProcessingRun.document_version_id == version.id,
               M.DocumentProcessingRun.run_type == E.ProcessingRunType.OCR)
    ).scalars().one()
    assert last.status is E.ProcessingRunStatus.FAILED
    assert last.error_code == "EXTRACTION_FAILED"
    assert "abandoned" in (last.error_message or "")

    # Idempotent: a second abandonment (two racing reconcilers, the lock aside)
    # finds the version concluded and does nothing.
    _abandon_ocr(db, version.id)
    runs = db.execute(
        select(func.count(M.DocumentProcessingRun.id))
        .where(M.DocumentProcessingRun.document_version_id == version.id,
               M.DocumentProcessingRun.run_type == E.ProcessingRunType.OCR)
    ).scalar_one()
    assert runs == 1

    # And no evidence appeared: abandonment asserts nothing about the text.
    rows = db.execute(
        select(M.DocumentEvidence)
        .where(M.DocumentEvidence.document_version_id == version.id)
    ).scalars().all()
    assert rows == []


def test_reconciliation_finds_exactly_the_interrupted_versions(db, store, monkeypatch):
    """PROCESSING is only ever committed by the deferred path, so at startup it
    means `interrupted` — and nothing COMPLETED or FAILED is ever re-touched."""
    from legalmind.worker.dispatch import interrupted_ocr_versions

    monkeypatch.setattr(parsing, "ocr_available", lambda: True)
    stuck = _ingest(db, store, build_pdf([mangle(READABLE_PAGE)]), defer_ocr=True)
    done = _ingest(db, store, build_pdf([READABLE_PAGE]), defer_ocr=True)

    monkeypatch.setattr(parsing, "ocr_available", lambda: False)
    failed = _ingest(db, store, build_pdf([mangle(READABLE_PAGE)]), defer_ocr=True)

    orphans = interrupted_ocr_versions(db)
    assert stuck.document_version.id in orphans
    assert done.document_version.id not in orphans
    assert failed.document_version.id not in orphans
