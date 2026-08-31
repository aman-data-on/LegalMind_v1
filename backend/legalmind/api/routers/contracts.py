"""Contracts and document upload — locked 49.3, 41.24, Step 34.

Ownership is the scope for a Contract (locked 42.3 ``owner_id``, 41.23): a list
returns only what a ``GET /{id}`` would return, and a ``GET /{id}`` for someone
else's contract is a 404, never a 403 — existence is itself a disclosure (47.7).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import func, select

from legalmind.api.deps import Guard, get_guard
from legalmind.api.envelope import data, paginated
from legalmind.api.errors import BusinessRuleRejected
from legalmind.api.pagination import Page, page_params, run
from legalmind.api.schemas import ContractCreate, ContractUpdate
from legalmind.api.serializers import serialize_contract, serialize_document_version
from legalmind.api.storage import get_storage
from legalmind.config import max_upload_bytes
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.ingestion.service import ingest_document
from legalmind.ingestion.storage import StorageBackend
from legalmind.security import permissions as P
from legalmind.worker.dispatch import dispatch_indexing

router = APIRouter(tags=["contracts"])


@router.get("/contracts")
def list_contracts(guard: Guard = Depends(get_guard),
                   page: Page = Depends(page_params)) -> dict:
    """49.6 — the same object-level scope as ``GET /contracts/{id}``."""
    guard.permission(P.CONTRACT_VIEW)
    stmt = select(M.Contract).where(M.Contract.owner_id == guard.user_id)
    rows, total = run(guard.db, stmt, page,
                      M.Contract.created_at.desc(), M.Contract.id.desc())
    summaries = _list_summaries(guard, [c.id for c in rows])
    payload = []
    for c in rows:
        item = serialize_contract(c)
        item.update(summaries.get(c.id, {"latest_version": None,
                                         "latest_analysis": None}))
        payload.append(item)
    return paginated(payload,
                     page=page.page, page_size=page.page_size, total=total)


def _list_summaries(guard: Guard, contract_ids: list[UUID]) -> dict[UUID, dict]:
    """Per-row `latest_version` / `latest_analysis` for the Documents list —
    2026-08-31 UX correction (Step 49 implementation addition, the #187
    precedent): the list answers "what did analysis find" instead of echoing a
    lifecycle enum. Three page-bounded grouped queries; no N+1.

    Permission-layered like every projection: version metadata needs
    `document.view`; the analysis block needs `review.view`; the
    classification counts inside it additionally need `finding.view` and are
    OMITTED (never nulled) without it — Step 24 r8's rule applied here.
    """
    if not contract_ids or P.DOCUMENT_VIEW not in guard.permissions:
        return {}
    versions = guard.db.execute(
        select(M.DocumentVersion)
        .where(M.DocumentVersion.contract_id.in_(contract_ids))
        .order_by(M.DocumentVersion.contract_id,
                  M.DocumentVersion.version_number.desc())
    ).scalars().all()
    latest_version: dict[UUID, M.DocumentVersion] = {}
    for version in versions:
        latest_version.setdefault(version.contract_id, version)

    out: dict[UUID, dict] = {}
    for cid, version in latest_version.items():
        out[cid] = {"latest_version": {
            "id": str(version.id),
            "version_number": version.version_number,
            "processing_status": version.processing_status.value,
        }, "latest_analysis": None}

    if P.REVIEW_VIEW not in guard.permissions or not latest_version:
        return out
    reviews = guard.db.execute(
        select(M.Review)
        .where(M.Review.document_version_id.in_(
            [v.id for v in latest_version.values()]))
        .order_by(M.Review.document_version_id,
                  M.Review.created_at.desc(), M.Review.id.desc())
    ).scalars().all()
    latest_review: dict[UUID, M.Review] = {}
    for r in reviews:
        latest_review.setdefault(r.document_version_id, r)

    counts: dict[UUID, dict[str, int]] = {}
    if latest_review and P.FINDING_VIEW in guard.permissions:
        grouped = guard.db.execute(
            select(M.Finding.review_id, M.Finding.classification, func.count())
            .where(M.Finding.review_id.in_([r.id for r in latest_review.values()]))
            .group_by(M.Finding.review_id, M.Finding.classification)
        ).all()
        for review_id, classification, n in grouped:
            counts.setdefault(review_id, {})[classification.value] = n

    for cid, version in latest_version.items():
        review = latest_review.get(version.id)
        if review is None:
            continue
        analysis = {
            "review_id": str(review.id),
            "review_status": review.status.value,
            "created_at": (review.created_at.isoformat()
                           if review.created_at else None),
            "completed_at": (review.completed_at.isoformat()
                             if review.completed_at else None),
        }
        if P.FINDING_VIEW in guard.permissions:
            analysis["classification_counts"] = counts.get(review.id, {})
        out[cid]["latest_analysis"] = analysis
    return out


@router.post("/contracts", status_code=201)
def create_contract(body: ContractCreate,
                    guard: Guard = Depends(get_guard)) -> dict:
    guard.permission(P.CONTRACT_CREATE)
    contract = M.Contract(owner_id=guard.user_id, name=body.name,
                          contract_type=body.contract_type,
                          status=E.ContractStatus.DRAFT)
    guard.db.add(contract)
    guard.db.flush()
    return data(serialize_contract(contract))


@router.get("/contracts/{contract_id}")
def get_contract(contract_id: UUID, guard: Guard = Depends(get_guard)) -> dict:
    """The contract with its document versions, newest first.

    `document_versions` is an implementation addition (2026-08-30, UI phase): a
    document-anchored workspace opened on a contract must be able to find its
    document through the API, and nothing listed versions — the legacy screen only
    ever showed the version it had just uploaded. Additive, same permission the
    contract already required (a version is reachable only through a contract the
    caller can see — 47.6 one level down), and the summary is the existing
    `serialize_document_version` shape, so nothing new is disclosed. Recorded in
    Step 49's implementation-additions section.
    """
    contract = guard.contract(contract_id, P.CONTRACT_VIEW)
    versions = guard.db.execute(
        select(M.DocumentVersion)
        .where(M.DocumentVersion.contract_id == contract.id)
        .order_by(M.DocumentVersion.version_number.desc(), M.DocumentVersion.id.desc())
    ).scalars().all()
    payload = serialize_contract(contract)
    payload["document_versions"] = [serialize_document_version(v) for v in versions]
    return data(payload)


@router.patch("/contracts/{contract_id}")
def update_contract(contract_id: UUID, body: ContractUpdate,
                    guard: Guard = Depends(get_guard)) -> dict:
    contract = guard.contract(contract_id, P.CONTRACT_UPDATE)
    if body.name is not None:
        contract.name = body.name
    if body.contract_type is not None:
        contract.contract_type = body.contract_type
    if body.status is not None:
        contract.status = body.status
    contract.updated_at = datetime.now(UTC)
    guard.db.flush()
    return data(serialize_contract(contract))


@router.post("/contracts/{contract_id}/document-versions", status_code=201)
async def upload_document_version(
    contract_id: UUID,
    request: Request,
    x_filename: str = Header(..., max_length=400),
    guard: Guard = Depends(get_guard),
    storage: StorageBackend = Depends(get_storage),
) -> dict:
    """Ingest one document version — locked Step 34, 42.4.

    **The body is the file itself**, with the declared type in ``Content-Type``
    and the original name in ``X-Filename``. Endpoint shape is outside the locked
    boundary (38.24), and this shape avoids adding a multipart parser to the path
    that handles untrusted input — locked 34.16 and Step 39's upload-validation
    item both argue for the smaller surface. The declared type is treated as a
    *claim*: ``validate_upload`` sniffs the magic bytes and rejects a mismatch.

    A duplicate is **reported, never silently suppressed** (34.5): whether a
    re-upload is a new contractual version is a business decision (Step 33.9).
    """
    guard.contract(contract_id, P.DOCUMENT_UPLOAD)

    declared_length = request.headers.get("content-length")
    limit = max_upload_bytes()
    if declared_length is not None and int(declared_length) > limit:
        raise BusinessRuleRejected(f"upload exceeds the {limit}-byte limit")
    payload = await request.body()
    if len(payload) > limit:
        raise BusinessRuleRejected(f"upload exceeds the {limit}-byte limit")
    if not payload:
        raise BusinessRuleRejected("the request body is empty")

    result = ingest_document(
        guard.db, storage,
        contract_id=contract_id,
        uploaded_by=guard.user_id,
        data=payload,
        filename=x_filename,
        declared_mime=request.headers.get("content-type", ""),
    )

    # Assist-lane indexing — AB-3 / AB-4, Gate section 5b unit A2. Additive and
    # non-authoritative: it builds a derived search index over evidence the parser has
    # already produced, and it can never fail this upload. `dispatch_indexing` swallows
    # its own faults for that reason, and the response below is unchanged either way —
    # no field reports index state, because a document is ingested whether or not a
    # derived index was built.
    dispatch_indexing(guard.db, result.document_version.id,
                      request_id=guard.request_id)

    return data({
        "document_version": serialize_document_version(result.document_version),
        "processing_run": {
            "id": str(result.processing_run.id),
            "run_type": result.processing_run.run_type.value,
            "status": result.processing_run.status.value,
            "processor_version": result.processing_run.processor_version,
            "error_code": result.processing_run.error_code,
        },
        "evidence_count": result.evidence_count,
        "duplicate_of": (str(result.duplicate_of)
                         if result.duplicate_of else None),
        # 34.9 / REC-07 — diagnostics only. They never become a legal conclusion.
        "diagnostics": result.diagnostics,
    })
