"""The hard Ask retrieval benchmark: the LIVE agent's seed search, scored with ZERO Gemini.

    python3 -m tools.hard_benchmark --db <url> [--json out.json] [--write-baseline]

Each question of `tests/assist_eval/hard_retrieval.json` goes through what a reader's
turn runs before the model plans anything: the brand decided in code (`agent.turn_brand`,
`AM-201`), then `search_knowledge` over the message. The connection is READ ONLY.

Metrics, per gold slot (a slot is met by any of its refs): recall@3 / @10 by the slot's
first position in what the model is shown, MRR, all slots met (complete), and per brand
case whether the other brand's policy was shown (wrong_brand). Missing cases (empty gold)
report how many records were still shown — the model, not this search, must say "not in
our sources". The release check: no metric may fall below the baseline.
"""
from __future__ import annotations

import argparse
import collections
import dataclasses
import fnmatch
import json
import pathlib
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from tools.rag_benchmark import PERMISSIONS

DATASET = pathlib.Path(__file__).resolve().parents[1] / "tests/assist_eval/hard_retrieval.json"
BASELINE = DATASET.with_name("hard_retrieval_baseline.json")


def matches(gold: str, ref: str) -> bool:
    """fnmatch, and a ref meets its own sub-sections (CONST:9 meets CONST:9.2, a statute
    gold names its Act by the title's prefix)."""
    if fnmatch.fnmatchcase(ref, gold) or ref.startswith((gold + ".", gold + "(")):
        return True
    if gold.startswith("STAT:") and ref.startswith("STAT:") and gold.count(":") >= 2:
        act, sec = gold[5:].rsplit(":", 1)
        ract, rsec = ref[5:].rsplit(":", 1)
        return ract.startswith(act) and fnmatch.fnmatchcase(rsec, sec)
    return False


def _rank(slot: list[str], shown: list[str]) -> int | None:
    """1-based rank WITHIN each gold ref's own source kind: the search returns its
    sources in fixed blocks, statutes last, and the model sees every block — a flat rank
    would put every statute past 3 (as `rag_benchmark._rank`)."""
    ranks = [i for g in slot
             for i, r in enumerate([s for s in shown
                                    if s.split(":")[0] == g.split(":")[0]], 1)
             if matches(g, r)]
    return min(ranks, default=None)


def score(case: dict, shown: list[str]) -> dict:
    """Pure: one case against the refs shown, in order."""
    ranks = [_rank(slot, shown) for slot in case["gold"]]
    return {"id": case["id"], "cat": case["cat"], "ranks": ranks,
            "wrong_brand": (any(matches(g, r) for g in case["must_not"] for r in shown)
                            if case.get("must_not") else None),
            "shown": shown}


def aggregate(rows: list[dict]) -> dict:
    slots = [k for r in rows for k in r["ranks"]]
    gold = [r for r in rows if r["ranks"]]
    brand = [r["wrong_brand"] for r in rows if r["wrong_brand"] is not None]

    def frac(xs):
        return round(sum(xs) / len(xs), 4) if xs else None
    return {"cases": len(rows), "slots": len(slots),
            "recall@3": frac([k is not None and k <= 3 for k in slots]),
            "recall@10": frac([k is not None and k <= 10 for k in slots]),
            "mrr": frac([1 / k if k else 0 for k in slots]),
            "complete": frac([all(r["ranks"]) for r in gold]),
            "wrong_brand": frac(brand),
            "missing_shown_avg": frac([len(r["shown"]) for r in rows if not r["ranks"]])}


def stable_refs(db, records) -> list[str]:
    """A published policy's ref carries its parent row id (`retrieval.py`); the set names
    it by source type and section heading (the breadcrumb's second part — a policy item
    has no section_path), which survive a re-ingest."""
    ids = [r.item_id for r in records if r.ref.startswith("PUB:") and r.item_id]
    rows = db.execute(text(
        "SELECT i.id::text, s.source_type, i.breadcrumb FROM assist.knowledge_items i "
        "JOIN assist.knowledge_sources s ON s.id = i.source_id "
        "WHERE i.id::text = ANY(:ids)"), {"ids": ids}).all() if ids else []
    path = {}
    for i, kind, crumb in rows:
        parts = (crumb or "").split(" · ")
        path[i] = f"{kind}:{parts[1] if len(parts) > 1 else parts[0]}"
    return [f"PUB:{path[r.item_id]}" if r.item_id in path else r.ref for r in records]


def seed_search(db, question: str) -> tuple[list[str], int]:
    """(shown refs, rescue-judge calls) — the turn's seed search (`agent.run_turn`)."""
    from legalmind.assist.agent import agent, tools
    ctx = tools.ToolContext(db, uuid.UUID(int=0), PERMISSIONS, uuid.UUID(int=0), None)
    ctx = dataclasses.replace(ctx, brand=agent.turn_brand(ctx, question, []),
                              brand_decided=True)
    found = tools.run(ctx, "search_knowledge",
                      {"query": question[:tools.MAX_QUERY_CHARS]}, rescue=True)
    calls = sum(q.rescue_called for q in (found.by_source or {}).values())
    return stable_refs(db, found.records), calls


def run(db) -> dict:
    rows, calls = [], 0
    for case in json.loads(DATASET.read_text())["cases"]:
        shown, n = seed_search(db, case["q"])
        calls += n
        rows.append(score(case, shown))
    by_cat = collections.defaultdict(list)
    for r in rows:
        by_cat[r["cat"]].append(r)
    return {"overall": aggregate(rows), "gemini_calls": calls,
            "by_category": {k: aggregate(v) for k, v in sorted(by_cat.items())},
            "cases": rows}


def regressions(now: dict, base: dict) -> list[str]:
    """Every metric worse than the baseline's (wrong_brand: higher is worse)."""
    out = []
    for k, b in base["overall"].items():
        v = now["overall"].get(k)
        if k in ("cases", "slots", "missing_shown_avg") or b is None or v is None:
            continue
        if (v > b) if k == "wrong_brand" else (v < b):
            out.append(f"{k} {b} -> {v}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--json")
    ap.add_argument("--write-baseline", action="store_true")
    args = ap.parse_args()
    engine = create_engine(args.db, future=True,
                           connect_args={"options": "-c default_transaction_read_only=on"})
    out = run(sessionmaker(bind=engine, future=True)())
    print("overall", json.dumps(out["overall"]), "gemini_calls", out["gemini_calls"])
    for cat, m in out["by_category"].items():
        print(f"  {cat}: {json.dumps(m)}")
    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(out, indent=1))
    if args.write_baseline:
        BASELINE.write_text(json.dumps(out, indent=1) + "\n")
        return 0
    if BASELINE.exists():
        worse = regressions(out, json.loads(BASELINE.read_text()))
        print("REGRESSED: " + "; ".join(worse) if worse else "no regression vs baseline")
        return 1 if worse else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
