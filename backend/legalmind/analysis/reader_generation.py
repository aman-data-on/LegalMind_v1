"""Two versions read by different reader generations, compared as one reader reads them
(batch 6 D1, AM-185 rider, 2026-11-20).

`legalmind-ingest-v12` numbers clauses and marks Word headings the v11 reader did not,
and stored evidence is never re-parsed (rule 16). So an MSA we sent before v12 and the
client's markup after it would differ in structure alone — phantom rows. Wherever two
versions are compared, the OLDER side's stored rows are re-read on read with today's
rules (`parsing.reread`): content, boundaries and evidence ids unchanged. A pair of one
generation (every answered pair before this batch) is untouched, so its rows and keys
cannot move.

The re-read is pinned per generation (`parsing.READER_ADDS`, R2-4): a pair is read up to
its newer side's generation, never by whatever reader ships later.
ponytail: a PDF block v12 would SPLIT at a glued number is not re-split.
"""
from __future__ import annotations

import math
import re
from dataclasses import replace
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from legalmind.db import models as M
from legalmind.db.lookup import latest_completed_run_id
from legalmind.ingestion.parsing import reread
from legalmind.mapping.engine import Clause

__all__ = ["REREAD_FROM", "as_one_reader", "generation", "older", "reread",
           "reread_clauses"]

_INGEST_N = re.compile(r"legalmind-ingest-v(\d+)$")
#: the reader generation whose numbering and heading rules `parsing.reread` replays
REREAD_FROM = 12


def generation(db: DBSession, version_id: UUID | None) -> float | None:
    """The reader generation that read the version; ``None`` id: a template blank parsed
    now (the newest reader); None when not recorded (nothing is re-read then)."""
    if version_id is None:
        return math.inf
    run_id = latest_completed_run_id(db, version_id)
    run = db.get(M.DocumentProcessingRun, run_id) if run_id else None
    m = _INGEST_N.match((run.processor_version or "") if run else "")
    return int(m.group(1)) if m else None


def older(db: DBSession, a: UUID | None, b: UUID | None
          ) -> tuple[UUID | None, float, float] | None:
    """Which side to re-read, with its generation and the newer side's — (id, since,
    upto); a template (``None``) is never older — or None when the two read alike (one
    generation, both new, or a generation unknown)."""
    ga, gb = generation(db, a), generation(db, b)
    if ga is None or gb is None or ga == gb or min(ga, gb) >= REREAD_FROM \
            or max(ga, gb) < REREAD_FROM:
        return None
    return (a, ga, gb) if ga < gb else (b, gb, ga)


def reread_clauses(db: DBSession, clauses: list[Clause], since: float,
                   upto: float) -> list[Clause]:
    """``clauses`` read as generation ``upto`` reads them (`parsing.reread`), each row's
    Word style read from its stored metadata."""
    E = M.DocumentEvidence
    meta: dict[UUID, dict | None] = dict(db.execute(
        select(E.id, E.evidence_metadata).where(
            E.id.in_([c.evidence_id for c in clauses]))).tuples().all())
    out = []
    for c in clauses:
        style = (meta.get(c.evidence_id) or {}).get("style")
        number, title, heading = reread(c.content or "", c.section_number,
                                        c.section_title, c.is_heading, style,
                                        since=since, upto=upto)
        out.append(replace(c, section_number=number, section_title=title,
                           is_heading=heading))
    return out


def as_one_reader(db: DBSession, a: UUID | None, b: UUID | None, ours: list[Clause],
                  theirs: list[Clause]) -> tuple[list[Clause], list[Clause]]:
    """(ours, theirs) — versions ``a`` and ``b`` — with the older side re-read."""
    found = older(db, a, b)
    if found is None:
        return ours, theirs
    side, since, upto = found
    return (reread_clauses(db, ours, since, upto), theirs) if side == a else \
        (ours, reread_clauses(db, theirs, since, upto))
