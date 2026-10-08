"""Ingest the supplied statutes into Domain C — `AM-32` r6/r7, `AM-47`.

Reads `backend/config/statutes/registry.json` (the provenance record the owner's supply
supports) and the files at `LEGALMIND_SOURCE_MATERIAL_DIR/<directory>/`. Refuses any
entry whose provenance is incomplete or whose file is absent; never fetches anything.

Run from `backend/`:

    python3 -m tools.ingest_statutes            # all registry entries, in place
    python3 -m tools.ingest_statutes --only IT_Act_2000.pdf

Blue-green re-ingest (`AM-125`) — operator CLI only, no HTTP surface:

    --stage               build a STAGED generation beside the live one (live untouched)
    --diff --out <path>   live vs STAGED report, written OUTSIDE the repository (54.6)
    --swap                one transaction: live -> STANDBY, STAGED -> live
    --rollback            the exact reverse: live -> STAGED, STANDBY -> live
    --retire              STANDBY -> WITHDRAWN once the rollback window closes

Nothing is ever deleted: retired rows keep the citations recorded against them.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from legalmind import config
from legalmind.assist.knowledge import statutes
from legalmind.assist.knowledge.statutes import (
    StatuteIngestRefused,
    ingest_statute,
    withdraw_statute,
)

REGISTRY = Path(__file__).resolve().parents[1] / "config" / "statutes" / "registry.json"
REPO = Path(__file__).resolve().parents[2]
SPOT_CHECKS = 10
EXCERPT = 160
FOOTNOTE_LINE = re.compile(r"(?mi)^\s*" + statutes._FOOTNOTE_HEAD.pattern)


def _ingest(db: Session, only: str | None, stage: bool) -> int:
    registry = json.loads(REGISTRY.read_text())
    base = Path(config.source_material_dir()) / registry["directory"]
    failures = 0
    for entry in registry["statutes"]:
        if only and entry["file"] != only:
            continue
        provenance = {k: registry[k] for k in ("supplied_by", "supplied_at", "source",
                                              "jurisdiction")}
        provenance.update({k: v for k, v in entry.items() if k != "file"})
        try:
            report = ingest_statute(db, path=base / entry["file"], provenance=provenance,
                                    stage=stage)
            db.commit()
            cut = report["dropped"]
            print(f"{entry['file']}: {report['sections']} sections in "
                  f"{report['chunks']} chunks, {report['embedded']} embedded, "
                  f"sha {report['file_sha256'][:12]}, {cut.footnotes} footnote and "
                  f"{cut.page_marks} page-mark blocks cut ({cut.chars} chars, "
                  f"sha {cut.sha256[:12]})" + (" — STAGED" if stage else "")
                  + (f", {report['citations_repointed']} citations repointed"
                     if report["citations_repointed"] else ""))
        except StatuteIngestRefused as exc:
            db.rollback()
            failures += 1
            # A refused STAGE leaves the live generation exactly as it is, and
            # withdraws the Act's earlier STAGED build so it can never be swapped in.
            withdrawn = withdraw_statute(db, path=base / entry["file"],
                                         provenance=provenance, stage=stage)
            db.commit()
            print(f"REFUSED {exc}" + (f" — {withdrawn} existing row(s) WITHDRAWN"
                                      if withdrawn else ""), file=sys.stderr)
    return 1 if failures else 0


def _generation(db: Session, where: str) -> dict[str, list]:
    schema = config.assist_schema()
    out: dict[str, list] = {}
    for r in db.execute(sql_text(f"""
            SELECT s.official_title, c.section_number, c.sub_section, c.content
              FROM "{schema}".statute_chunks c JOIN "{schema}".statutes s
                ON s.id = c.statute_id
             WHERE {where} ORDER BY s.official_title, c.ordinal""")).all():
        out.setdefault(r.official_title, []).append(r)
    return out


def _sizes(chunks: list) -> str:
    n = sorted(len(c.content) for c in chunks) or [0]
    return f"{n[len(n) // 2]}/{n[int(len(n) * .95)]}/{n[-1]}"


def _excerpt(a: str, b: str) -> tuple[str, str]:
    """Short excerpts of two texts around their first difference (54.6: excerpts only)."""
    at = next((i for i, (x, y) in enumerate(zip(a, b, strict=False)) if x != y),
              min(len(a), len(b)))
    lo = max(0, at - EXCERPT // 4)
    return (" ".join(a[lo:lo + EXCERPT].split()), " ".join(b[lo:lo + EXCERPT].split()))


def diff_report(db: Session, *, seed: int = 0) -> str:
    """Live vs STAGED, per Act: chunk counts, % changed — a STAGED chunk is unchanged
    only when a live chunk has its (section, sub-section) AND its content — sizes,
    sections added and lost, footnote-headed chunks, and seeded spot checks."""
    live = _generation(db, statutes._live_sql())
    staged = _generation(db, "s.status = 'STAGED'")
    lines = ["# Statute re-ingest — live vs STAGED", "",
             f"parser `{statutes.STATUTE_CHUNKING_ALGORITHM_VERSION}`; sizes are "
             "p50/p95/max characters; footnote = a line opening with an amendment note.",
             "", "| Act | chunks | changed | sizes live | sizes staged | footnote chunks "
             "| sections added | sections lost |", "|---|---|---|---|---|---|---|---|"]
    changed_all: list[tuple] = []
    totals = [0, 0, 0, 0, 0]
    for title in sorted(set(live) | set(staged)):
        old, new = live.get(title, []), staged.get(title, [])
        held = {(c.section_number, c.sub_section, c.content) for c in old}
        changed = [c for c in new if (c.section_number, c.sub_section, c.content) not in held]
        by_key = {(c.section_number, c.sub_section): c for c in reversed(old)}
        changed_all += [(title, c, by_key.get((c.section_number, c.sub_section)))
                        for c in changed]
        osec, nsec = {c.section_number for c in old}, {c.section_number for c in new}
        fo = sum(1 for c in old if FOOTNOTE_LINE.search(c.content))
        fn = sum(1 for c in new if FOOTNOTE_LINE.search(c.content))
        totals = [t + x for t, x in zip(totals, (len(old), len(new), len(changed), fo, fn),
                                        strict=True)]
        lines.append(f"| {title[:60]} | {len(old)} → {len(new)} | "
                     f"{len(changed) / max(1, len(new)):.1%} | {_sizes(old)} | "
                     f"{_sizes(new)} | {fo} → {fn} | {', '.join(sorted(nsec - osec)) or '—'}"
                     f" | {', '.join(sorted(osec - nsec)) or '—'} |")
    lines += ["", f"**Total:** chunks {totals[0]} → {totals[1]}; changed {totals[2]} "
              f"({totals[2] / max(1, totals[1]):.1%}); footnote chunks {totals[3]} → "
              f"{totals[4]}.", "", f"## {SPOT_CHECKS} spot checks (seed {seed})", ""]
    for title, new_chunk, old_chunk in random.Random(seed).sample(
            changed_all, min(SPOT_CHECKS, len(changed_all))):
        unit = f"s. {new_chunk.section_number}{' ' + new_chunk.sub_section if new_chunk.sub_section else ''}"
        before, after = _excerpt(old_chunk.content if old_chunk else "", new_chunk.content)
        lines += [f"- **{title[:60]}, {unit}**", f"  - before: `{before or '(no such unit)'}`",
                  f"  - after: `{after}`"]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="ingest one registry file name")
    mode = parser.add_mutually_exclusive_group()
    for flag in ("--stage", "--diff", "--swap", "--rollback", "--retire"):
        mode.add_argument(flag, action="store_true")
    parser.add_argument("--out", type=Path, help="--diff: report path, outside the repo")
    args = parser.parse_args()
    if args.diff and (not args.out or args.out.resolve().is_relative_to(REPO)):
        parser.error("--diff needs --out <path> OUTSIDE the repository (locked 54.6)")
    engine = create_engine(config.database_url())
    with Session(engine) as db:
        if args.diff:
            args.out.write_text(diff_report(db))
            print(f"diff written to {args.out}")
            return 0
        if args.swap or args.rollback:
            incoming, outgoing = (("STAGED", "STANDBY") if args.swap
                                  else ("STANDBY", "STAGED"))
            try:
                n = statutes.flip(db, incoming=incoming, outgoing=outgoing)
            except StatuteIngestRefused as exc:
                print(f"REFUSED {exc}", file=sys.stderr)
                return 1
            db.commit()
            print(f"{n} statutes: {incoming} -> live, live -> {outgoing}")
            return 0
        if args.retire:
            n = statutes.retire(db)
            db.commit()
            print(f"{n} STANDBY statute rows -> WITHDRAWN (nothing deleted)")
            return 0
        return _ingest(db, args.only, args.stage)


if __name__ == "__main__":
    raise SystemExit(main())
