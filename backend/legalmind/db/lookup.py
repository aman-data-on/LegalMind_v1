"""Narrowing a lookup that a NOT NULL foreign key already guarantees.

`Session.get` returns `Row | None` because that is true in general. It is *not* true
when the id came from a NOT NULL foreign key: locked 42.x makes `evaluations.finding_id`,
`findings.review_id` and the rest NOT NULL, so a missing row means referential
integrity has been violated, not that the caller asked for something optional.

Both readings currently produce a failure. The difference is where:

```text
without   finding.review_id  ->  AttributeError: 'NoneType' has no attribute
                                 'review_id', several frames from the cause
with      MissingReference: findings row for evaluation <id> does not exist
```

For an append-only legal record the second is worth having. It also lets the type
checker see what the schema already guarantees, so the narrowing is stated once here
rather than assumed at each of ten call sites.

This raises rather than returning a default **by design**. A default would be a
fabricated legal object (rule 15, ENG-09).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from legalmind.db import models as M
from legalmind.domain import enums as E


class MissingReference(Exception):
    """A row referenced by a NOT NULL foreign key does not exist.

    Never a request error and never a Finding: the database is inconsistent. Surfaces
    as a 500, which is correct — nothing the caller did caused it and nothing they can
    change will fix it.
    """


def must_exist[T](row: T | None, what: str,
                  referenced_by: UUID | str | None = None) -> T:
    if row is None:
        where = f" referenced by {referenced_by}" if referenced_by else ""
        raise MissingReference(f"{what}{where} does not exist")
    return row


def latest_completed_run_id(db: DBSession, document_version_id: UUID) -> UUID | None:
    """The ONE processing run whose evidence IS the document (42.5; P-8, 2026-09-06).

    Every reader of a version's evidence — the document pane, mapping, unmatched
    provisions, version comparison — scopes to this run. Failed and in-flight
    attempts are kept for history (42.5) and contribute no rows; a version with
    two COMPLETED runs (an OCR retry, a future REPROCESS) shows the latest one
    only, never a merge of two segmentations. Lives in `db` because the mapping
    and analysis cores may import `db` and `domain` and nothing else
    (`test_import_boundaries.LAYERING`).

    Ordering (ENG-11): `created_at` defaults to now(), which is TRANSACTION start —
    two runs created in one transaction share it. `started_at` is set per run from
    the application clock, and `id` is the final deterministic tiebreak.
    """
    return db.execute(
        select(M.DocumentProcessingRun.id)
        .where(M.DocumentProcessingRun.document_version_id == document_version_id,
               M.DocumentProcessingRun.status == E.ProcessingRunStatus.COMPLETED)
        .order_by(M.DocumentProcessingRun.started_at.desc().nullslast(),
                  M.DocumentProcessingRun.created_at.desc(),
                  M.DocumentProcessingRun.id.desc())
        .limit(1)
    ).scalar_one_or_none()
