"""The lawyer-review benchmark (R2 slice S1, owner 2026-11-16) — zero model.

Scores what LegalMind surfaced on a client's markup against a real lawyer's review of
that markup: which of the lawyer's rows a point touches (by clause), how many of the rows
with a REJECT, how many points touch no row (noise), and — when points carry an
``origin`` (step 0) — the noise that is "already in our MSA".

The gold review is real legal material: it is read from
``$LEGALMIND_SOURCE_MATERIAL_DIR/lawyer-reviews/`` (gitignored, 54.6) and never copied
into the repo; without it the tool says so and exits 0 (a skip, never a pass).

Gold format, one row per line: ``Sr | clause | client change | VERDICTS``.
Points JSON: either ``{"points": [{"clauses": [...], "origin"?: ..., "code"?: ...}]}``
or an engine run ``{code: {"classification": ..., "cited": [[clause, page], ...]}}``
(MATCH points are not raised and are skipped).

    python3 -m tools.lawyer_benchmark --points run.json [--gold NAME.md] [--json]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

_REF = re.compile(r"(?<![\d.])(\d{1,2}(?:\.\d{1,2}){0,3})(?![\d])")


def gold_dir() -> Path:
    return Path(os.environ.get("LEGALMIND_SOURCE_MATERIAL_DIR", "/nonexistent")) \
        / "lawyer-reviews"


def parse_gold(text: str) -> list[dict[str, Any]]:
    """Each numbered row: its clause refs (the clause column and every ref a verdict
    names) and whether the lawyer rejected any part of it."""
    rows = []
    for line in text.splitlines():
        cells = [c.strip() for c in line.split("|")]
        if len(cells) < 4 or not cells[0].isdigit():
            continue
        verdict = " | ".join(cells[3:])
        refs = set(_REF.findall(cells[1]))
        refs |= {m.group(1) for m in re.finditer(
            r"(?:^|\.\s+)(\d{1,2}(?:\.\d{1,2}){1,3})(?:\([a-z]\))?\s+(?:ACCEPT|REJECT)",
            verdict)}
        rows.append({"sr": int(cells[0]), "clauses": sorted(refs),
                     "reject": "REJECT" in verdict})
    return rows


def load_points(data: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(data.get("points"), list):
        return data["points"]
    if isinstance(data.get("changes"), list):           # a `negotiation.changes` listing
        return [{"clauses": [c["clause"]["number"]] if (c.get("clause") or {}).get(
                    "number") else [], "effect": c.get("effect_for_us"),
                 "auto": bool((c.get("answer") or {}).get("auto"))}
                for c in data["changes"]]
    return [{"code": code, "clauses": [c[0] for c in v.get("cited") or ()],
             **({"origin": v["origin"]} if v.get("origin") else {})}
            for code, v in data.items()
            if isinstance(v, dict) and v.get("classification") != "MATCH"]


def touches(point: str, gold: str) -> bool:
    """The same clause, or one inside the other — never a bare top-level number, which
    would touch every row of its section."""
    if point == gold or (gold.startswith(point + ".") and "." in point):
        return True
    return point.startswith(gold + ".")


def score(gold: list[dict[str, Any]], points: list[dict[str, Any]]) -> dict[str, Any]:
    hit_rows: set[int] = set()
    noise: list[dict[str, Any]] = []
    rejects = {g["sr"] for g in gold if g["reject"]}
    auto_on_reject: list[dict[str, Any]] = []
    for p in points:
        rows = {g["sr"] for g in gold
                if any(touches(c, ref) for c in p["clauses"] for ref in g["clauses"])}
        hit_rows |= rows
        # Priyen's rule (2026-11-16): a point accepted automatically on a row the lawyer
        # REJECTED is a false auto-accept — must be zero
        if p.get("auto") and rows & rejects:
            auto_on_reject.append({**p, "reject_rows": sorted(rows & rejects)})
        if not rows:
            noise.append(p)
    origins: dict[str, int] = {}
    for p in noise:
        origins[p.get("origin") or "unlabelled"] = \
            origins.get(p.get("origin") or "unlabelled", 0) + 1
    return {"rows": len(gold), "rows_touched": len(hit_rows),
            "reject_rows": len(rejects), "reject_rows_touched": len(hit_rows & rejects),
            "points": len(points), "points_on_a_row": len(points) - len(noise),
            "noise": len(noise), "noise_by_origin": origins,
            "missed_reject_rows": sorted(rejects - hit_rows),
            "auto_accepted": sum(bool(p.get("auto")) for p in points),
            "to_legal": sum(not p.get("auto") for p in points),
            "auto_on_reject_rows": auto_on_reject}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--points", required=True, type=Path)
    ap.add_argument("--gold", default=None,
                    help="file name in lawyer-reviews/ (default: the only one there)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    found = sorted(gold_dir().glob("*.md")) if gold_dir().is_dir() else []
    path = gold_dir() / Path(args.gold).name if args.gold else (
        found[0] if len(found) == 1 else gold_dir() / "(name one with --gold)")
    if not path.is_file():
        print(f"SKIPPED: the lawyer review is not here ({path}); set "
              "LEGALMIND_SOURCE_MATERIAL_DIR to the legal-docs folder.")
        return 0
    result = score(parse_gold(path.read_text()), load_points(json.loads(
        args.points.read_text())))
    if args.json:
        print(json.dumps(result, indent=1))
    else:
        print(f"Lawyer rows touched: {result['rows_touched']}/{result['rows']}  ·  "
              f"REJECT rows touched: {result['reject_rows_touched']}/"
              f"{result['reject_rows']}  ·  points on a row: "
              f"{result['points_on_a_row']}/{result['points']}  ·  noise: "
              f"{result['noise']} {result['noise_by_origin']}  ·  auto-accepted: "
              f"{result['auto_accepted']}, to Legal: {result['to_legal']}, auto on a "
              f"REJECT row: {len(result['auto_on_reject_rows'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
