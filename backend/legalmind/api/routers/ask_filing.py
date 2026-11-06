"""File an Ask attachment into a contract — `AM-269` r2 (AB-150, 2026-11-02), R10.

A file attached in Ask stays the chat's (`AM-133` r2–r3) until the reader presses
"File into contract" and names the contract. Then, and only then, it enters the
ordinary upload pipeline as that contract's next version, declared CLIENT_MODIFIED, and
the filing is audited. Nothing in Ask calls this by itself.

Chat material keeps no raw bytes (A-15), so the reader's browser sends the file again
and the server accepts it only if it is byte-for-byte the attached one (its SHA-256).
The contracts offered are the ones the caller may negotiate — owner or collaborator,
through `require_contract_negotiable` — and nothing about any other contract is said.
"""
from __future__ import annotations

import hashlib
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy import or_, select, text
from starlette.concurrency import run_in_threadpool

from legalmind import config, notifications
from legalmind.api.deps import CommitBeforeResponse, Guard, get_guard
from legalmind.api.envelope import data
from legalmind.api.errors import BusinessRuleRejected
from legalmind.api.routers.assist import _attachments_on, _visible_conversation
from legalmind.api.routers.contracts import (
    _decode_percent_encoded_filename,
    _ingest_upload,
    read_bounded,
)
from legalmind.api.serializers import serialize_document_version
from legalmind.api.storage import get_storage
from legalmind.config import max_upload_bytes
from legalmind.db import models as M
from legalmind.ingestion.storage import StorageBackend
from legalmind.ingestion.validation import DOCX_MIME, PDF_MIME
from legalmind.security import audit
from legalmind.security import permissions as P
from legalmind.security.errors import NotVisible

router = APIRouter(tags=["assist"], route_class=CommitBeforeResponse)

CLIENT_MODIFIED = "CLIENT_MODIFIED"


def _fileable(guard: Guard, conversation_id: UUID,
              attachment_id: UUID) -> tuple[dict, str]:
    """(conversation, sha256) of a READY Word/PDF file in the caller's own chat; any
    other attachment id is the conversation's 404."""
    _attachments_on()
    conversation = _visible_conversation(guard, conversation_id)
    row = guard.db.execute(text(
        f'SELECT content_sha256 FROM "{config.assist_schema()}".conversation_attachments '
        "WHERE id = :a AND conversation_id = :c AND kind = 'FILE' AND status = 'READY' "
        "AND mime_type IN (:pdf, :docx)"),
        {"a": attachment_id, "c": conversation_id, "pdf": PDF_MIME,
         "docx": DOCX_MIME}).first()
    if row is None:
        raise NotVisible("attachment", attachment_id)
    return conversation, row[0]


@router.get("/conversations/{conversation_id}/attachments/{attachment_id}/file-targets")
def file_targets(conversation_id: UUID, attachment_id: UUID,
                 guard: Guard = Depends(get_guard)) -> dict:
    """The contracts this file may be filed into — the chat's own contract first."""
    guard.permission(P.DOCUMENT_UPLOAD)
    conversation, _ = _fileable(guard, conversation_id, attachment_id)
    mine = [M.Contract.owner_id == guard.user_id]
    if guard.department_id is not None:
        # AM-280 r2: a collaborator only while still in the owner's department (the
        # caller is active: they are signed in) — as `reviews.py` scopes it
        mine.append(M.Contract.id.in_(
            select(M.ContractCollaborator.contract_id)
            .join(M.Contract, M.Contract.id == M.ContractCollaborator.contract_id)
            .join(M.User, M.User.id == M.Contract.owner_id)
            .where(M.ContractCollaborator.user_id == guard.user_id,
                   M.User.department_id == guard.department_id)))
    rows = guard.db.execute(
        select(M.Contract.id, M.Contract.name)
        .where(or_(*mine), M.Contract.archived_at.is_(None))
        .order_by((M.Contract.id == conversation["contract_id"]).desc(),
                  M.Contract.updated_at.desc())
        .limit(50)).all()
    return data([{"id": str(r[0]), "name": r[1]} for r in rows])


@router.post("/conversations/{conversation_id}/attachments/{attachment_id}/file",
             status_code=201)
async def file_attachment(conversation_id: UUID, attachment_id: UUID, request: Request,
                          contract_id: UUID = Query(...),
                          x_filename: str = Header(..., max_length=400),
                          guard: Guard = Depends(get_guard),
                          storage: StorageBackend = Depends(get_storage)) -> dict:
    """The body is the attached file again (A-15 keeps no bytes); it must match."""
    await run_in_threadpool(guard.permission, P.DOCUMENT_UPLOAD)
    _, digest = await run_in_threadpool(_fileable, guard, conversation_id, attachment_id)
    await run_in_threadpool(guard.contract_negotiable, contract_id, P.DOCUMENT_UPLOAD)
    limit = max_upload_bytes()
    payload = await read_bounded(request, limit, f"upload exceeds the {limit}-byte limit")
    if hashlib.sha256(payload).hexdigest() != digest:
        raise BusinessRuleRejected("this is not the file attached in this chat")
    return await run_in_threadpool(
        _file, guard, storage, contract_id, attachment_id, payload,
        _decode_percent_encoded_filename(x_filename),
        request.headers.get("content-type", ""))


def _file(guard: Guard, storage: StorageBackend, contract_id: UUID, attachment_id: UUID,
          payload: bytes, filename: str, mime: str) -> dict:
    result = _ingest_upload(guard, storage, contract_id, payload, filename, mime)
    version = guard.db.get(M.DocumentVersion,
                           UUID(result["data"]["document_version"]["id"]))
    assert version is not None
    version.doc_metadata = {**(version.doc_metadata or {}),
                            "version_role": CLIENT_MODIFIED}
    guard.db.flush()
    audit.record(guard.db, action=audit.ASSIST_ATTACHMENT_FILED, entity_type="contract",
                 entity_id=contract_id, actor_id=guard.user_id,
                 request_id=guard.request_id,
                 after={"attachment_id": str(attachment_id),
                        "document_version_id": str(version.id),
                        "version_role": CLIENT_MODIFIED, "file_hash": version.file_hash})
    contract = guard.db.get(M.Contract, contract_id)
    assert contract is not None
    notifications.client_returned(guard.db, contract, actor_id=guard.user_id)
    result["data"]["document_version"] = serialize_document_version(version)
    return result
