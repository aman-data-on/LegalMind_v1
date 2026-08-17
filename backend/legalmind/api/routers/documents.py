"""Document versions — locked 49.3, 47.6 traversal.

A Document Version is reachable only through a Contract the caller can see, which
is the 47.6 traversal applied one level down: knowing the id is never sufficient
(41.24).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from legalmind.api.deps import Guard, get_guard
from legalmind.api.envelope import data
from legalmind.api.serializers import serialize_document_version
from legalmind.api.storage import get_storage
from legalmind.ingestion.storage import StorageBackend
from legalmind.security import permissions as P
from legalmind.security.errors import NotVisible

router = APIRouter(tags=["documents"])


@router.get("/document-versions/{document_version_id}")
def get_document_version(document_version_id: UUID,
                         guard: Guard = Depends(get_guard)) -> dict:
    version = guard.document_version(document_version_id, P.DOCUMENT_VIEW)
    return data(serialize_document_version(version))


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
