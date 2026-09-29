"""(Re)build the canonical Constitution source model — `AM-79`, roadmap PHASE 1.

Idempotent: an unchanged Constitution file (same SHA-256) is left alone.
Usage:  python3 -m tools.ingest_constitution
"""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from legalmind import config
from legalmind.assist import constitution


def main() -> int:
    with Session(create_engine(config.database_url())) as db:
        print(constitution.ingest(db))
        db.commit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
