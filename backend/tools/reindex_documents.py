"""Re-index document versions under the current chunker, keeping every citation.

`AM-27` r4 chunks are derived and disposable; `answer_citations` are not (rule 17). A
plain `reindex=True` used to delete-and-reinsert, cascading citations away — measured
2026-09-10: 130 of 136 document citations sat on rows the `clause-aware-2` chunker wrote.
`store.replace_chunks` now updates a clause's row in place and hands an absorbed
fragment's citations to the clause that absorbed it, so this tool is safe to run over a
live index. Each version is its own transaction; a failure stops the run with the
versions before it committed.

Usage:  python3 -m tools.reindex_documents [--dry-run] [--version-id UUID ...]
                                           [--only-older-than clause-aware-4]

`--dry-run` prints what would change (chunk counts, short-chunk share, citations
touched) and rolls back. Identifiers and counts only — never text (locked 53.3).
"""

from __future__ import annotations

import argparse
import sys
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from legalmind import config
from legalmind.assist.chunking import CHUNKING_ALGORITHM_VERSION, MIN_CHUNK_CHARS
from legalmind.assist.indexing import index_document_version


def _profile(db: Session, dv: UUID) -> tuple[int, int, int]:
    """(chunks, chunks under MIN_CHUNK_CHARS, citations) for one version."""
    schema = config.assist_schema()
    row = db.execute(text(f"""
        SELECT count(*), count(*) FILTER (WHERE length(content) < :m),
               (SELECT count(*) FROM "{schema}".answer_citations ac
                  JOIN "{schema}".chunks c2 ON c2.id = ac.chunk_id
                 WHERE c2.document_version_id = :dv)
          FROM "{schema}".chunks WHERE document_version_id = :dv
    """), {"dv": dv, "m": MIN_CHUNK_CHARS}).one()
    return int(row[0]), int(row[1]), int(row[2])


def _targets(db: Session, version_ids: list[UUID], older_than: str | None) -> list[UUID]:
    schema = config.assist_schema()
    if version_ids:
        return version_ids
    sql = f'SELECT DISTINCT document_version_id FROM "{schema}".chunks'
    if older_than:
        sql += " WHERE chunking_algorithm_version <> :v"
    return [r[0] for r in db.execute(text(sql), {"v": older_than}).all()]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--version-id", type=UUID, nargs="*", default=[])
    ap.add_argument("--only-older-than", default=CHUNKING_ALGORITHM_VERSION,
                    help="skip versions already on this chunker version ('' for none)")
    args = ap.parse_args(argv)

    engine = create_engine(config.database_url())
    totals = [0, 0, 0, 0, 0, 0]
    with Session(engine) as db:
        targets = _targets(db, args.version_id, args.only_older_than or None)
        print(f"{len(targets)} document version(s) to re-index under "
              f"{CHUNKING_ALGORITHM_VERSION}{' (dry run)' if args.dry_run else ''}")
        for dv in targets:
            before = _profile(db, dv)
            result = index_document_version(db, dv, reindex=True)
            after = _profile(db, dv)
            if result.skipped:
                print(f"  {str(dv)[:8]}  skipped: {result.reason}")
                db.rollback()
                continue
            print(f"  {str(dv)[:8]}  chunks {before[0]:>4} -> {after[0]:<4} "
                  f"short {before[1]:>4} -> {after[1]:<4} "
                  f"citations {before[2]:>3} -> {after[2]:<3}"
                  + ("  LOST" if after[2] < before[2] else ""))
            for i, v in enumerate((*before, *after)):
                totals[i] += v
            if args.dry_run:
                db.rollback()
            else:
                db.commit()
    b, a = totals[:3], totals[3:]

    def pct(share: int, total: int) -> str:
        return f"{100 * share / total:.1f}%" if total else "n/a"

    print(f"total chunks {b[0]} -> {a[0]}; under {MIN_CHUNK_CHARS} chars "
          f"{b[1]} ({pct(b[1], b[0])}) -> {a[1]} ({pct(a[1], a[0])}); "
          f"citations {b[2]} -> {a[2]}")
    return 0 if a[2] >= b[2] else 1


if __name__ == "__main__":
    sys.exit(main())
