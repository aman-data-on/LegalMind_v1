"""Roadmap PHASE 0 — the multi-source golden benchmark, scored with ZERO Gemini calls.

    python3 -m tools.rag_benchmark --db <url> [--json out.json] [--write-baseline]

Replays the production NO-DOCUMENT path of `service._ask` exactly — `routing.plan`,
the primary Domain A / Domain C searches with the production limits, then
`service._consult_fallbacks` — over `tests/assist_eval/rag_benchmark.json`, and scores
every gold SLOT at the stage where it failed (roadmap §16: retrieval judged on its own,
not through the final answer). Document retrieval is scored by `tools/probe_targeting.py`
over the ratified 77-question set; this benchmark is the cross-source half.

The connection is opened READ ONLY (`default_transaction_read_only`), so pointing it at
the production database measures what readers get today and cannot write a row.

Failure taxonomy (per unsatisfied gold slot, first that applies):
  SOURCE_NOT_INDEXED  every ref is a Constitution section — no retrieval path exists
  SOURCE_MISSING      the ref'd standard/section is not in the corpus at all
  ROUTE_SHORT_CIRCUIT the route returned before retrieval (comparison, unmet, capability…)
  ROUTE_MISSED        the ref'd domain was neither primary nor a consulted fallback
  RANK_CUTOFF         in the 50-deep diagnostic pool, cut by the production limit
  RETRIEVAL_MISS      not even in the 50-deep pool
and per satisfied slot RANK_LOW (rank > 3). Per case: WRONG_SOURCE (a must_not ref
shown) and FALSE_ADMISSION (a must-refuse case shown any evidence).
Generation-stage codes (scored from PHASE 10): UNSUPPORTED_CLAIM · USER_ASSERTION_AS_EVIDENCE
· HISTORICAL_AS_POLICY · MISSING_DOCUMENT_FILLED · BLENDED_SOURCES · VERIFIER_FALSE_REJECT.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import pathlib
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from legalmind.assist import (
    constitution,
    positions,
    routing,
    service,
    statutes,
    understanding,
)

DATASET = pathlib.Path(__file__).resolve().parents[1] / "tests/assist_eval/rag_benchmark.json"
BASELINE = DATASET.with_name("rag_benchmark_baseline.json")
PERMISSIONS = frozenset({"assist.ask", "configuration.view", "legal_position.view"})
WIDE = 50
DOMAIN_OF = {"POS": routing.Domain.POSITIONS.value, "STAT": routing.Domain.STATUTES.value,
             "CONST": "CONSTITUTION"}


def _act(title: str) -> str:
    return title.removeprefix("The ")


def ref_matches(ref: str, hit_ref: str) -> bool:
    """`hit_ref` is what a hit IS (POS:code / STAT:title:section); `ref` may be a prefix
    Act name and a `*` section."""
    kind, _, rest = ref.partition(":")
    hkind, _, hrest = hit_ref.partition(":")
    if kind != hkind:
        return False
    if rest == "*":
        return True
    if kind != "STAT":
        return rest == hrest
    act, _, sec = rest.rpartition(":")
    hact, _, hsec = hrest.rpartition(":")
    return hact.startswith(act) and (sec == "*" or sec == hsec)


def hit_refs(pos_hits, stat_hits) -> list[str]:
    """Display order `routing.ordered` gives the answer: positions before statutes."""
    return ([f"POS:{h.standard_code}" for h in pos_hits]
            + [f"STAT:{_act(h.official_title)}:{h.section_number}" for h in stat_hits])


def _rank(refs_in_slot, hits: list[str]) -> int | None:
    """1-based rank WITHIN the ref's own domain list — sources are never merged."""
    best = None
    for ref in refs_in_slot:
        dom = [h for h in hits if h.startswith(ref.split(":")[0] + ":")]
        for i, h in enumerate(dom, 1):
            if ref_matches(ref, h):
                best = i if best is None else min(best, i)
                break
    return best


def score_case(case: dict, shown: list[str], wide: list[str], searched: set[str],
               exists, short_circuit: bool) -> dict:
    """Pure: everything already retrieved. `exists(ref)` says whether the corpus holds it."""
    slots = []
    for slot in case["gold"]:
        rank = _rank(slot, shown)
        code = None
        if rank is None:
            if all(r.startswith("CONST:") for r in slot):
                code = "SOURCE_NOT_INDEXED"
            elif not any(exists(r) for r in slot if not r.startswith("CONST:")):
                code = "SOURCE_MISSING"
            elif short_circuit:
                code = "ROUTE_SHORT_CIRCUIT"
            elif not any(DOMAIN_OF[r.split(":")[0]] in searched for r in slot):
                code = "ROUTE_MISSED"
            elif _rank(slot, wide) is not None:
                code = "RANK_CUTOFF"
            else:
                code = "RETRIEVAL_MISS"
        elif rank > 3:
            code = "RANK_LOW"
        slots.append({"rank": rank, "code": code})
    wrong = sorted({h for h in shown for r in case["must_not"] if ref_matches(r, h)})
    relevant = [any(ref_matches(r, h) for slot in case["gold"] for r in slot) for h in shown]
    ideal = min(len(case["gold"]), 5)
    dcg = sum(1 / math.log2(i + 2) for i, rel in enumerate(relevant[:5]) if rel)
    idcg = sum(1 / math.log2(i + 2) for i in range(ideal))
    return {"id": case["id"], "category": case["category"], "golden": case.get("golden", False),
            "must_refuse": bool(case.get("answer", {}).get("refuse")),
            "slots": slots, "wrong_source": wrong,
            "false_admission": bool(case.get("answer", {}).get("refuse")) and bool(shown),
            "ndcg5": round(dcg / idcg, 4) if idcg else None, "shown": shown}


def retrieve(db, case: dict) -> tuple[list[str], list[str], set[str], bool, str]:
    """The production no-document path of `service._ask`, retrieval only."""
    question = case["question"]
    resolved = question
    asked = understanding.understand(question)
    if case.get("after") and (asked.follow_up or asked.exact_text):
        _, resolved = service._resolve_follow_up([(uuid.uuid4(), case["after"])], question)
    route = routing.plan(resolved, has_document=False, permissions=PERMISSIONS,
                         statutes_available=statutes.available(db),
                         statute_jurisdictions=statutes.jurisdictions(db))
    if route.general_knowledge or route.capability or route.comparison or route.unmet:
        return [], [], set(), True, resolved
    domains = tuple(d.value for d in route.domains)
    pos = (positions.search_positions(db, query=resolved, permissions=PERMISSIONS,
                                      limit=service.POSITION_LIMIT,
                                      allow_relax=service._relax_allowed(route))
           if route.has(routing.Domain.POSITIONS) else [])
    stat = (statutes.search_statutes(db, query=resolved, permissions=PERMISSIONS,
                                     include_superseded=route.include_superseded)
            if route.has(routing.Domain.STATUTES) else [])
    domains, pos, stat = service._consult_fallbacks(
        db, uuid.uuid4(), resolved, route, domains, pos, stat, PERMISSIONS, None)
    wide = hit_refs(
        positions.search_positions(db, query=resolved, permissions=PERMISSIONS, limit=WIDE),
        statutes.search_statutes(db, query=resolved, permissions=PERMISSIONS, limit=WIDE,
                                 include_superseded=True))
    return hit_refs(pos, stat), wide, set(domains), False, resolved


def constitution_lane(db, question: str, limit: int) -> list[str]:
    """PHASE 3 diagnostic: the Constitution's own retrieval records, which no
    production route reaches until PHASE 7. Scored apart so the production numbers
    stay the production numbers."""
    return [f"CONST:{h.section_path}" for h in constitution.search(
        db, query=question, permissions=PERMISSIONS, limit=limit)]


def corpus_refs(db) -> list[str]:
    rows = db.execute(text(
        "SELECT 'POS:' || standard_code FROM assist.position_chunks UNION "
        "SELECT 'STAT:' || regexp_replace(s.official_title, '^The ', '') || ':' || c.section_number "
        "FROM assist.statute_chunks c JOIN assist.statutes s ON s.id = c.statute_id")).scalars()
    return list(rows)


def aggregate(results: list[dict]) -> dict:
    slots = [s for r in results for s in r["slots"]]
    gold_cases = [r for r in results if r["slots"]]

    def frac(xs):
        return round(sum(xs) / len(xs), 4) if xs else None
    first = [r["slots"][0]["rank"] for r in gold_cases]
    return {
        "cases": len(results), "slots": len(slots),
        "recall@3": frac([s["rank"] is not None and s["rank"] <= 3 for s in slots]),
        "recall@10": frac([s["rank"] is not None and s["rank"] <= 10 for s in slots]),
        "hit@1": frac([rk == 1 for rk in first]),
        "mrr": frac([1 / s["rank"] if s["rank"] else 0 for s in slots]),
        "ndcg@5": frac([r["ndcg5"] for r in gold_cases if r["ndcg5"] is not None]),
        "multi_source_complete": frac([all(s["rank"] for s in r["slots"])
                                       for r in gold_cases if len(r["slots"]) > 1]),
        "wrong_source_rate": frac([bool(r["wrong_source"]) for r in results]),
        "false_admission_rate": frac([r["false_admission"] for r in results if r["must_refuse"]]),
        "failure_codes": dict(collections.Counter(s["code"] for s in slots if s["code"])),
    }


def run(db) -> dict:
    cases = json.loads(DATASET.read_text())["cases"]
    held = corpus_refs(db)

    def exists(ref):
        return any(ref_matches(ref, h) for h in held)
    results = []
    const_ranks: list[int | None] = []
    for c in cases:
        shown, wide, searched, short, resolved = retrieve(db, c)
        results.append(score_case(c, shown, wide, searched, exists, short))
        const_slots = [s for s in c["gold"] if any(r.startswith("CONST:") for r in s)]
        if const_slots:
            lane = constitution_lane(db, resolved, 10)
            for slot in const_slots:
                const_ranks.append(_rank([r for r in slot if r.startswith("CONST:")], lane))
                results[-1].setdefault("constitution_lane", []).append(const_ranks[-1])
    by_cat = collections.defaultdict(list)
    for r in results:
        by_cat[r["category"]].append(r)
    def at(k):
        return round(sum(1 for r in const_ranks if r and r <= k) / len(const_ranks), 4) \
            if const_ranks else None
    return {"overall": aggregate(results),
            "constitution_lane": {"slots": len(const_ranks), "recall@3": at(3),
                                  "recall@6": at(6), "recall@10": at(10),
                                  "mrr": round(sum(1 / r for r in const_ranks if r)
                                               / len(const_ranks), 4)
                                  if const_ranks else None},
            "golden": aggregate([r for r in results if r["golden"]]),
            "by_category": {k: aggregate(v) for k, v in sorted(by_cat.items())},
            "cases": results}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--json")
    ap.add_argument("--write-baseline", action="store_true")
    ap.add_argument("--label", default="")
    args = ap.parse_args()
    engine = create_engine(args.db, future=True,
                           connect_args={"options": "-c default_transaction_read_only=on"})
    out = run(sessionmaker(bind=engine, future=True)()) | {"label": args.label}
    for name in ("overall", "golden", "constitution_lane"):
        print(name, json.dumps(out[name]))
    for cat, m in out["by_category"].items():
        print(f"  {cat}: n={m['cases']} r@3={m['recall@3']} mrr={m['mrr']} "
              f"wrong={m['wrong_source_rate']} codes={m['failure_codes']}")
    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(out, indent=1))
    if args.write_baseline:
        BASELINE.write_text(json.dumps(out, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
