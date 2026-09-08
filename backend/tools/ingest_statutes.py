"""Ingest the supplied statutes into Domain C — `AM-32` r6/r7, `AM-47`.

Reads `backend/config/statutes/registry.json` (the provenance record the owner's supply
supports) and the files at `LEGALMIND_SOURCE_MATERIAL_DIR/<directory>/`. Refuses any
entry whose provenance is incomplete or whose file is absent; never fetches anything.

Run from `backend/`:

    python3 -m tools.ingest_statutes            # all registry entries
    python3 -m tools.ingest_statutes --only IT_Act_2000.pdf
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from legalmind import config
from legalmind.assist.statutes import StatuteIngestRefused, ingest_statute

REGISTRY = Path(__file__).resolve().parents[1] / "config" / "statutes" / "registry.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="ingest one registry file name")
    args = parser.parse_args()
    registry = json.loads(REGISTRY.read_text())
    base = Path(config.source_material_dir()) / registry["directory"]
    engine = create_engine(config.database_url())
    failures = 0
    with Session(engine) as db:
        for entry in registry["statutes"]:
            if args.only and entry["file"] != args.only:
                continue
            provenance = {k: registry[k] for k in ("supplied_by", "supplied_at", "source",
                                                  "jurisdiction")}
            provenance.update({k: v for k, v in entry.items() if k != "file"})
            try:
                report = ingest_statute(db, path=base / entry["file"], provenance=provenance)
                db.commit()
                print(f"{entry['file']}: {report['chunks']} sections, "
                      f"{report['embedded']} embedded, sha {report['file_sha256'][:12]}")
            except StatuteIngestRefused as exc:
                db.rollback()
                failures += 1
                print(f"REFUSED {exc}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
