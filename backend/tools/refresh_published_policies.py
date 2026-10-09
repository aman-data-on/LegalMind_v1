"""Bring Ask's copy of the published policies up to the website — `AM-130` (AB-74).

    python3 -m tools.refresh_published_policies            # fetch the 8 live pages
    python3 -m tools.refresh_published_policies --from DIR # ingest saved <key>.html files

Run daily by `ops/production/legalmind-published-policies.timer`. Unchanged pages
write nothing; a changed page becomes CURRENT and is audited. Prints one line per
policy — key, changed or not, version — never policy text. Exit 1 if any page failed.
"""
from __future__ import annotations

import argparse
import datetime
import pathlib

from legalmind.assist.knowledge import published
from legalmind.db.session import new_session


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="folder", type=pathlib.Path,
                    help="ingest saved pages instead of fetching")
    args = ap.parse_args(argv)
    fetcher = published.fetch if args.folder is None else (
        lambda p: (args.folder / f"{p.key}.html").read_text())
    read_on = None
    if args.folder is not None:            # saved pages keep the date they were read
        try:
            read_on = datetime.date.fromisoformat(args.folder.name)
        except ValueError:
            read_on = None
    db = new_session()
    try:
        results = published.refresh(db, fetcher=fetcher, read_on=read_on)
    finally:
        db.close()
    for r in results:
        state = r.get("error") or ("CHANGED" if r["changed"] else "unchanged")
        print(f"{r['policy']:20} {state} {r.get('version', '')}")
    return 1 if any("error" in r for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
