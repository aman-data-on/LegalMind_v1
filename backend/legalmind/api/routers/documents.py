"""Document versions — locked 49.3, 47.6 traversal.

A Document Version is reachable only through a Contract the caller can see, which
is the 47.6 traversal applied one level down: knowing the id is never sufficient
(41.24).
"""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import func, select, text

from legalmind import config
from legalmind.analysis.version_comparison import (
    ComparisonNotPossible,
    compare_versions,
)
from legalmind.api.deps import Guard, get_guard
from legalmind.api.envelope import data, paginated
from legalmind.api.errors import BusinessRuleRejected, Conflict
from legalmind.api.pagination import Page, page_params, run
from legalmind.api.schemas import DocumentVersionDeclare
from legalmind.api.serializers import serialize_document_version, serialize_evidence
from legalmind.api.storage import get_storage
from legalmind.assist import store as assist_store
from legalmind.db import models as M
from legalmind.db.lookup import latest_completed_run_id
from legalmind.domain import enums as E
from legalmind.ingestion.service import process_document_version
from legalmind.ingestion.storage import StorageBackend
from legalmind.security import audit
from legalmind.security import permissions as P
from legalmind.security.errors import NotVisible
from legalmind.worker.dispatch import (
    dispatch_indexing,
    dispatch_ocr,
    version_lock_key,
)

router = APIRouter(tags=["documents"])


@router.get("/document-versions/{document_version_id}")
def get_document_version(document_version_id: UUID,
                         guard: Guard = Depends(get_guard)) -> dict:
    version = guard.document_version_readable(document_version_id, P.DOCUMENT_VIEW)
    payload = serialize_document_version(version)
    # Whether the assist lane can search this version yet — plain counts, so the
    # client derives "ready", "lexical only" or "not indexed" itself. Deliberately
    # NOT a new state vocabulary: `AM-29` r1 reserves the assist lane's one axis for
    # answer state, and an index-readiness enum would be a second one by another
    # name. Counts also survive a model change honestly (embedded < chunks).
    payload["assist_index"] = {
        "chunks": assist_store.count_chunks(guard.db, version.id),
        "embedded_chunks": assist_store.count_embeddings(guard.db, version.id),
    }
    return data(payload)


@router.patch("/document-versions/{document_version_id}")
def declare_document_version(document_version_id: UUID, body: DocumentVersionDeclare,
                             guard: Guard = Depends(get_guard)) -> dict:
    """Declare a version's source, counterparty and effective date (2026-09-06).

    Writes into locked 42.4's `metadata` JSONB — no column, no migration — the
    route owner Q2 chose for Document Type (the `D-3` precedent). Owner-scoped
    like every write (`guard.document_version`: department and Legal scope are
    READ scopes; an archived contract refuses with 409, AB-12 r6).

    **Immutable once reviewed.** Locked 33.7 / 34.15 r3 make a version immutable
    once a Review exists, and the owner ruled (2026-09-06) that declared metadata
    follows the same line: it may be corrected only while no Review exists. So
    the check is on Reviews, not on analysis outcome — a DRAFT Review freezes it.

    Declared, never inferred: nothing here reads the document. The upload
    endpoint's body is the file itself (38.24), which is why the declaration is
    a second call rather than a header — a counterparty name is exactly the kind
    of non-ASCII value that broke the `X-Filename` header path (2026-09-03).
    """
    version = guard.document_version(document_version_id, P.DOCUMENT_UPLOAD)
    reviewed = guard.db.execute(
        select(M.Review.id).where(M.Review.document_version_id == version.id).limit(1)
    ).first()
    if reviewed is not None:
        raise Conflict("this version has a Review; its declared metadata is fixed "
                       "(locked 33.7) — upload a new version to change it")

    # A NEW dict, not a mutation: the column is plain JSONB (no MutableDict), so
    # SQLAlchemy only sees the change when the attribute is reassigned.
    meta = dict(version.doc_metadata or {})
    for key in body.model_fields_set:
        value = getattr(body, key)
        if value is None:
            meta.pop(key, None)             # sent as null: cleared, and OMITTED
        else:
            meta[key] = value.isoformat() if isinstance(value, date) else value
    version.doc_metadata = meta or None
    guard.db.flush()
    return data(serialize_document_version(version))


def _reprocess_blockers(db, version: M.DocumentVersion) -> list[str]:
    """Why a version may NOT be re-read in place — Option C (owner, 2026-09-06):
    "never silently mutate versions already relied upon by reviews, citations or
    evidence". Every reader now shows ONE run (P-8), so a re-read would move the
    document out from under anything anchored to the current rows: a Review's
    Findings and Evaluations (their evidence would vanish from the pane), an Ask
    answer's citations (they point at this reading's chunks), and Key Obligations
    (anchored to evidence ids). Each is named so the reader knows why, and what
    to do instead — upload the document again as a new version."""
    if version.processing_status is E.ProcessingStatus.PROCESSING:
        return ["it is still being processed"]
    schema = config.assist_schema()
    checks: tuple[tuple[Any, dict[str, Any], str], ...] = (
        (select(M.Review.id).where(M.Review.document_version_id == version.id).limit(1),
         {}, "a Review relies on its current reading"),
        (text(f'SELECT 1 FROM "{schema}".answer_citations ac '
              f'JOIN "{schema}".chunks c ON c.id = ac.chunk_id '
              f'WHERE c.document_version_id = :dv LIMIT 1'),
         {"dv": version.id}, "an answer in Ask cites its current text"),
        (text(f'SELECT 1 FROM "{schema}".obligation_extractions '
              f'WHERE document_version_id = :dv LIMIT 1'),
         {"dv": version.id}, "its Key Obligations are anchored to its current text"),
    )
    return [why for stmt, params, why in checks
            if db.execute(stmt, params).first() is not None]


@router.post("/document-versions/{document_version_id}/reprocess", status_code=201)
def reprocess_document_version(
    document_version_id: UUID,
    guard: Guard = Depends(get_guard),
    storage: StorageBackend = Depends(get_storage),
) -> dict:
    """Re-read a version's preserved original with the CURRENT parser — Phase 5,
    Option C (owner, 2026-09-06).

    A NEW `REPROCESS` processing run (locked 42.5's run type, unused until now)
    over the bytes 34.5 preserved. The file is never touched and no existing
    evidence row is rewritten or deleted (rule 17): the earlier run stays as
    history, and — because every reader scopes to the latest COMPLETED run
    (P-8) — the new reading simply becomes the document. Refused with 409, and
    the reason, while anything relies on the current reading; the way forward
    then is a new version by re-upload, exactly as before this existed.

    Owner-only under `document.upload` (`guard.document_version`), 409 on an
    archived contract (AB-12 r6), audited (`document.reprocessed`). A FAILED
    re-read changes nothing for readers, so the version keeps the statuses its
    standing reading earned rather than inheriting the failed attempt's.
    """
    version = guard.document_version(document_version_id, P.DOCUMENT_UPLOAD)

    # One re-read per version, database-wide (2026-09-06). The SAME advisory-lock
    # key the OCR job takes, so a re-read and a background OCR pass exclude each
    # other rather than each only itself — they write runs and evidence for the
    # same version. The TRANSACTION-scoped variant is the correct one here and
    # the session-scoped one is correct there: locked 43.26 makes this whole
    # request one transaction, so `pg_try_advisory_xact_lock` is held across
    # every write below and released at exactly the commit that makes the new
    # run visible — leaving no window in which the lock is gone but the run is
    # not yet readable. Postgres keeps both variants in one lock space, so the
    # two paths still conflict. Never blocks: a second caller is told to wait.
    if not guard.db.execute(
        text("SELECT pg_try_advisory_xact_lock(:key)"),
        {"key": version_lock_key(document_version_id)},
    ).scalar():
        raise Conflict("this version is already being re-read; wait for that to finish")

    # Under the lock, deliberately: a blocker check that ran before it would be
    # the check-then-act race the lock exists to close.
    blockers = _reprocess_blockers(guard.db, version)
    if blockers:
        raise Conflict("this version cannot be re-read in place: " + "; ".join(blockers)
                       + ". Upload the document again as a new version instead.")

    previous_run = latest_completed_run_id(guard.db, version.id)
    standing = (version.processing_status, version.extraction_status)
    run = process_document_version(guard.db, storage, version,
                                   run_type=E.ProcessingRunType.REPROCESS, defer_ocr=True)
    run.run_metadata = {**(run.run_metadata or {}),
                        "reprocess_of": str(previous_run) if previous_run else None}
    if run.status is E.ProcessingRunStatus.FAILED and previous_run is not None:
        version.processing_status, version.extraction_status = standing
    guard.db.flush()
    audit.record(
        guard.db, action=audit.DOCUMENT_REPROCESSED,
        entity_type="document_version", entity_id=version.id,
        actor_id=guard.user_id, request_id=guard.request_id,
        before={"processing_run_id": str(previous_run) if previous_run else None},
        after={"processing_run_id": str(run.id), "run_status": run.status.value},
    )

    if version.processing_status is E.ProcessingStatus.PROCESSING:
        dispatch_ocr(version.id, request_id=guard.request_id)   # the OCR job re-indexes
    elif run.status is E.ProcessingRunStatus.COMPLETED:
        # The superseded reading's chunks go with it (the `AM-27` r5 principle);
        # indexing then rebuilds over the new run's rows, as an upload would.
        assist_store.delete_chunks(guard.db, version.id)
        dispatch_indexing(guard.db, version.id, request_id=guard.request_id)

    evidence_count = guard.db.execute(
        select(func.count(M.DocumentEvidence.id))
        .where(M.DocumentEvidence.processing_run_id == run.id)).scalar_one()
    return data({
        "document_version": serialize_document_version(version),
        "processing_run": {
            "id": str(run.id), "run_type": run.run_type.value,
            "status": run.status.value, "processor_version": run.processor_version,
            "error_code": run.error_code,
        },
        "evidence_count": evidence_count,
        "duplicate_of": None,
        "diagnostics": list((run.run_metadata or {}).get("diagnostics", [])),
    })


@router.get("/document-versions/{document_version_id}/evidence")
def list_document_evidence(document_version_id: UUID,
                           guard: Guard = Depends(get_guard),
                           page: Page = Depends(page_params)) -> dict:
    """The document as the pipeline read it — every Evidence row, in reading order.

    The same 47.6 traversal and the same `document.view` permission as the version
    itself: seeing the document and seeing what the parser extracted from it are
    one act (a citation is an Evidence row, and a Finding's `evidence_refs` point
    here). Not in 49.3's table — an implementation addition recorded in
    `permission_map.IMPLEMENTATION_ADDED_ENDPOINTS` and AUTO_MODE_DECISIONS.md.

    Ordering is reading order with a stable tiebreaker (49.6): page, then offset,
    then id, with pages the parser could not number (OCR fragments) last.
    """
    version = guard.document_version_readable(document_version_id, P.DOCUMENT_VIEW)
    # Scoped to the latest COMPLETED run (P-8, 2026-09-06), like every other
    # reader: a retry or a future REPROCESS must never render two segmentations
    # merged. No completed run yet → no rows, exactly as before.
    stmt = select(M.DocumentEvidence).where(
        M.DocumentEvidence.document_version_id == version.id,
        M.DocumentEvidence.processing_run_id
        == latest_completed_run_id(guard.db, version.id))
    rows, total = run(guard.db, stmt, page,
                      M.DocumentEvidence.page_number.asc().nulls_last(),
                      M.DocumentEvidence.start_offset.asc().nulls_last(),
                      M.DocumentEvidence.id.asc())
    return paginated([serialize_evidence(e) for e in rows],
                     page=page.page, page_size=page.page_size, total=total)


@router.get("/document-versions/{document_version_id}/content")
def download_document_version(
    document_version_id: UUID,
    guard: Guard = Depends(get_guard),
    storage: StorageBackend = Depends(get_storage),
) -> Response:
    """Return the preserved original bytes — locked 34.2/34.5.

    ``document.download`` is a permission distinct from ``document.view``: seeing
    that a version exists and taking a copy of the counterparty's contract are
    different acts, and Step 47's catalogue separates them.
    """
    version = guard.document_version_readable(document_version_id, P.DOCUMENT_DOWNLOAD)
    if not storage.exists(version.storage_key):
        # The row exists but the object does not. Rendering this as the standard
        # 404 keeps storage state from being probeable and keeps the body
        # identical to every other 404 (49.5 r1).
        raise NotVisible("document content not available")
    return Response(
        content=storage.get(version.storage_key),
        media_type=version.mime_type,
        headers={
            # `attachment` so a PDF or DOCX is never rendered inline in the
            # application's own origin.
            "Content-Disposition":
                f'attachment; filename="{_safe_filename(version.original_filename)}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


def _safe_filename(name: str) -> str:
    """The stored name came from an untrusted upload; strip anything that could
    break out of the header (34.16)."""
    cleaned = "".join(c for c in name if c.isalnum() or c in "._- ")
    return cleaned.strip() or "document"


@router.get("/contracts/{contract_id}/version-comparison")
def compare_document_versions(
    contract_id: UUID,
    before: UUID = Query(..., description="the earlier document version"),
    after: UUID = Query(..., description="the later document version"),
    guard: Guard = Depends(get_guard),
) -> dict:
    """Clause-level comparison of two versions of one Contract — locked 33.15.

    Locked 33.15 asks for this and fixes the method: deterministic section
    comparison, explicitly **not** LLM/RAG. Locked PROD-04 puts `compare` in an
    ordinary User's hands, so the permission is `document.view` — the same
    permission that lets the caller read both versions, which is all a comparison
    discloses.

    Step 33 r19 and locked 33.16 are the boundary, and they are enforced by what
    this endpoint CANNOT return: no Finding, no Classification, no Rule Outcome,
    no verdict field. Where the newer version already has Findings, the ones
    landing in a changed clause are quoted beside it so the reader can see that
    the engine has something to say there — but that Finding was produced by the
    evaluator against a pinned snapshot, and a comparison never becomes one.

    Both versions resolve through the READ rule (ownership or `REC-09` Legal
    scope), so a Legal reviewer comparing the negotiation history of a document
    they are reviewing gets the same answer its owner does — and anyone else
    gets the same 404 either version would give on its own.
    """
    contract = guard.contract_readable(contract_id, P.DOCUMENT_VIEW)
    earlier = guard.db.get(M.DocumentVersion, before)
    later = guard.db.get(M.DocumentVersion, after)
    for version in (earlier, later):
        # 47.6 one level down: a version is reachable only through a Contract the
        # caller can see, and naming a version of someone else's contract must
        # not be distinguishable from naming one that does not exist (SEC-07).
        if version is None or version.contract_id != contract.id:
            raise NotVisible("document version not found")
    assert earlier is not None and later is not None
    try:
        return data(compare_versions(guard.db, earlier, later))
    except ComparisonNotPossible as exc:
        raise BusinessRuleRejected(str(exc)) from exc
