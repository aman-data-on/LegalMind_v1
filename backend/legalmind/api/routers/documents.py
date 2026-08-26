"""Document versions — locked 49.3, 47.6 traversal.

A Document Version is reachable only through a Contract the caller can see, which
is the 47.6 traversal applied one level down: knowing the id is never sufficient
(41.24).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select

from legalmind.api.deps import Guard, get_guard
from legalmind.api.envelope import data, paginated
from legalmind.api.pagination import Page, page_params, run
from legalmind.api.serializers import serialize_document_version, serialize_evidence
from legalmind.api.storage import get_storage
from legalmind.assist import store as assist_store
from legalmind.db import models as M
from legalmind.ingestion.storage import StorageBackend
from legalmind.security import permissions as P
from legalmind.security.errors import NotVisible

router = APIRouter(tags=["documents"])


@router.get("/document-versions/{document_version_id}")
def get_document_version(document_version_id: UUID,
                         guard: Guard = Depends(get_guard)) -> dict:
    version = guard.document_version(document_version_id, P.DOCUMENT_VIEW)
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
    version = guard.document_version(document_version_id, P.DOCUMENT_VIEW)
    stmt = select(M.DocumentEvidence).where(
        M.DocumentEvidence.document_version_id == version.id)
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
    version = guard.document_version(document_version_id, P.DOCUMENT_DOWNLOAD)
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
