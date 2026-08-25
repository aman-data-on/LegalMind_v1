"""Indexing a document version — the assist lane's only write path over a document.

Reads committed `document_evidence` and writes `<assist>.chunks`. It writes nothing
else, and by `AM-25` r2 it *cannot*: the assist database role holds no INSERT or UPDATE
grant on `findings`, `evaluations`, `legal_decisions`, the configuration tables, or any
other authoritative table. That is a grant, not a convention, and it does not depend on
this module being correct.

--------------------------------------------------------------------------
Idempotent by refusal, not by overwrite
--------------------------------------------------------------------------
Re-indexing is *not* the default, and that is a deliberate choice against the obvious
implementation. Deleting and re-inserting chunks cascades to `answer_citations`, so a
silent re-index would invalidate citations already recorded against the removed chunks —
an answer whose sources have quietly vanished. So an already-indexed version is a no-op
unless the caller explicitly asks to reindex.

Nothing cites a chunk yet, so this costs nothing today. It is written now because the
cheap version of this decision is the one made before there is data to lose.

--------------------------------------------------------------------------
A failed index must never fail an ingestion
--------------------------------------------------------------------------
Chunks are derived and disposable; Evidence is authoritative. An upload that parsed
successfully has done the thing that matters, and refusing it because a derived index
could not be built would let the assist lane break the authoritative path — the exact
inversion `AM-25` r1 and Step 38's rule 21 exist to prevent. `index_safely` is therefore
the seam callers on the ingestion path use, and it swallows and logs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from legalmind.assist import store
from legalmind.assist.chunking import CHUNKING_ALGORITHM_VERSION, chunk_evidence
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.observability.logs import log_event


@dataclass(frozen=True)
class IndexResult:
    document_version_id: UUID
    chunks_written: int
    skipped: bool
    reason: str | None = None


def index_document_version(db: DBSession, document_version_id: UUID, *,
                           reindex: bool = False) -> IndexResult:
    """Chunk a document version's committed evidence into the assist schema.

    Does not commit; the caller owns the transaction, as the ingestion layer does.
    """
    existing = store.count_chunks(db, document_version_id)
    if existing and not reindex:
        return IndexResult(document_version_id, 0, True,
                           f"already indexed ({existing} chunks)")

    version = db.get(M.DocumentVersion, document_version_id)
    if version is None:
        # Not an error worth raising: the enqueuing transaction may simply have rolled
        # back. The same posture the analysis task takes for a Review that is not there.
        return IndexResult(document_version_id, 0, True, "document version not found")

    # Only a successfully-processed version has evidence worth indexing. A FAILED
    # extraction has nothing, and a PARTIAL one has what was genuinely extracted —
    # which is indexable, because locked 34.10 represents partial extraction
    # explicitly rather than pretending it succeeded.
    if version.extraction_status is E.ExtractionStatus.FAILED:
        return IndexResult(document_version_id, 0, True, "extraction failed")

    rows = db.execute(
        select(M.DocumentEvidence)
        .where(M.DocumentEvidence.document_version_id == document_version_id)
        # Ordered so chunk ordinals are stable across runs. `id` is the tiebreaker
        # rather than nothing at all: without it two evidence rows sharing a page and
        # offset could come back in either order, and the chunk sequence would depend
        # on the query plan.
        .order_by(M.DocumentEvidence.page_number.nulls_first(),
                  M.DocumentEvidence.start_offset.nulls_first(),
                  M.DocumentEvidence.id)
    ).scalars().all()

    if not rows:
        return IndexResult(document_version_id, 0, True, "no evidence to index")

    if existing and reindex:
        store.delete_chunks(db, document_version_id)

    chunks = chunk_evidence(list(rows))
    written = store.write_chunks(db, document_version_id, chunks)

    # Deliberately in the assist signal namespace, never beside `workflow.decisions.*`
    # or `authz.*`: mixing a high-volume derived-index signal into the low-volume
    # legal-workflow stream makes the latter harder to read for no gain. Identifiers
    # and counts only — no clause text, per locked 53.3.
    log_event("assist.index.completed",
              document_version_id=str(document_version_id),
              evidence_rows=len(rows), chunks_written=written,
              algorithm=CHUNKING_ALGORITHM_VERSION)
    return IndexResult(document_version_id, written, False)


def index_safely(db: DBSession, document_version_id: UUID) -> IndexResult:
    """Index, but never let a failure reach the caller.

    For the ingestion path. A derived index is not permitted to fail an upload whose
    parsing succeeded — see this module's docstring. The failure is logged as an
    operational one so it is visible and countable, not swallowed into silence.
    """
    try:
        return index_document_version(db, document_version_id)
    except Exception as exc:
        log_event("assist.index.failed", level=logging.WARNING,
                  document_version_id=str(document_version_id),
                  error=type(exc).__name__, operational_failure=True)
        return IndexResult(document_version_id, 0, True,
                           f"indexing failed: {type(exc).__name__}")
