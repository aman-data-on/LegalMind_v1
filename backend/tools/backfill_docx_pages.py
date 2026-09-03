"""Backfill page numbers onto EXISTING DOCX evidence rows — 2026-09-02.

`legalmind-ingest-v2` reads DOCX page numbers from the file's own pagination
record; rows written by v1 have `page_number = NULL`. This tool fills that one
column for already-uploaded versions, under guarantees that keep rule 17
(reproducibility) intact:

* It re-parses the PRESERVED original (write-once storage) with the current
  parser and requires a 1:1 match — same count, same content, same offsets —
  against the stored rows before writing anything. Any mismatch aborts the
  whole version untouched.
* It writes ONLY `page_number`, and only where it is NULL. Content, offsets,
  sections, ids, findings and decisions are untouchable by construction.
* No legal output reads `page_number` except as a monotonic secondary sort key
  (verified 2026-09-02: `analysis/unmatched.py`, assist ordering — and the
  fill is monotonic over the same offset order, so no ordering changes).
* Dry-run by default; `--execute` writes.

Usage:
    python tools/backfill_docx_pages.py --contract-id <uuid> [--execute]
"""

from __future__ import annotations

import argparse
import sys
from uuid import UUID

sys.path.insert(0, ".")

from sqlalchemy import select

from legalmind.config import storage_root
from legalmind.db import models as M
from legalmind.db.session import session_factory
from legalmind.ingestion import parsing
from legalmind.ingestion.storage import LocalFilesystemStorage
from legalmind.ingestion.validation import DOCX_MIME


def backfill(contract_id: UUID, *, execute: bool) -> int:
    storage = LocalFilesystemStorage(storage_root())
    factory = session_factory()
    with factory() as db, db.begin():
        versions = db.scalars(
            select(M.DocumentVersion)
            .where(M.DocumentVersion.contract_id == contract_id,
                   M.DocumentVersion.mime_type == DOCX_MIME)
            .order_by(M.DocumentVersion.version_number)
        ).all()
        if not versions:
            print("No DOCX versions on that contract; nothing to do.")
            return 0

        for version in versions:
            rows = db.scalars(
                select(M.DocumentEvidence)
                .where(M.DocumentEvidence.document_version_id == version.id)
                .order_by(M.DocumentEvidence.start_offset)
            ).all()
            result = parsing.parse_docx(storage.get(version.storage_key))

            if result.pagination_source is None:
                print(f"v{version.version_number}: the file carries no pagination "
                      "record — honestly nothing to backfill.")
                continue

            if len(result.segments) != len(rows):
                print(f"v{version.version_number}: REFUSED — parser produced "
                      f"{len(result.segments)} segments but {len(rows)} rows are "
                      "stored. This version was not written by an equivalent "
                      "segmentation; backfilling could mislabel evidence.")
                continue

            mismatches = [
                (row.id, seg.start_offset)
                for row, seg in zip(rows, result.segments, strict=True)
                if row.content != seg.content or row.start_offset != seg.start_offset
            ]
            if mismatches:
                print(f"v{version.version_number}: REFUSED — {len(mismatches)} "
                      "row(s) differ from the re-parse; not touching anything.")
                continue

            fills = sum(1 for row, seg in zip(rows, result.segments, strict=True)
                        if row.page_number is None and seg.page_number is not None)
            conflicts = [row.id for row, seg in zip(rows, result.segments, strict=True)
                         if row.page_number is not None
                         and row.page_number != seg.page_number]
            if conflicts:
                print(f"v{version.version_number}: REFUSED — {len(conflicts)} rows "
                      "already carry a DIFFERENT page number; never overwriting.")
                continue

            print(f"v{version.version_number}: {result.pagination_source}, "
                  f"{result.pages_total} pages; {fills} of {len(rows)} rows to fill"
                  f"{' — DRY RUN, nothing written' if not execute else ''}.")
            if execute:
                for row, seg in zip(rows, result.segments, strict=True):
                    if row.page_number is None and seg.page_number is not None:
                        row.page_number = seg.page_number
                db.flush()
                print(f"v{version.version_number}: written.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--contract-id", required=True, type=UUID)
    ap.add_argument("--execute", action="store_true",
                    help="write the fills (default: dry run)")
    args = ap.parse_args()
    raise SystemExit(backfill(args.contract_id, execute=args.execute))
