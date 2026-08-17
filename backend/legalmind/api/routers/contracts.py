"""Contracts and document upload — locked 49.3, 41.24, Step 34.

Ownership is the scope for a Contract (locked 42.3 ``owner_id``, 41.23): a list
returns only what a ``GET /{id}`` would return, and a ``GET /{id}`` for someone
else's contract is a 404, never a 403 — existence is itself a disclosure (47.7).
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import select

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

router = APIRouter(tags=["contracts"])


@router.get("/contracts")
def list_contracts(guard: Guard = Depends(get_guard),
                   page: Page = Depends(page_params)) -> dict:
    """49.6 — the same object-level scope as ``GET /contracts/{id}``."""
    guard.permission(P.CONTRACT_VIEW)
    stmt = select(M.Contract).where(M.Contract.owner_id == guard.user_id)
    rows, total = run(guard.db, stmt, page,
                      M.Contract.created_at.desc(), M.Contract.id.desc())
    return paginated([serialize_contract(c) for c in rows],
                     page=page.page, page_size=page.page_size, total=total)


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
    return data(serialize_contract(guard.contract(contract_id, P.CONTRACT_VIEW)))


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
    contract.updated_at = datetime.now(timezone.utc)
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
