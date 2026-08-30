"""(Re)build Domain A position chunks from the ratified Company Standards.

`AM-32` r3: chunks derive from published `company_standard_versions` rows, which the
import tool (`tools.import_ratified_standards`) must have written first — this tool
refuses otherwise rather than inventing a position (rule 21). Idempotent: each run
deletes a standard's existing chunks and re-chunks the current version, so a
republished standard is one re-run away from a correct search surface.

Usage:  python3 -m tools.chunk_standards
"""

from __future__ import annotations

import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from legalmind import config
from legalmind.assist.positions import PositionChunkingRefused, chunk_ratified_standards


def main() -> int:
    engine = create_engine(config.database_url())
    with Session(engine) as db:
        try:
            lines = chunk_ratified_standards(db)
        except PositionChunkingRefused as exc:
            print(f"REFUSED: {exc}", file=sys.stderr)
            return 1
        db.commit()
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
