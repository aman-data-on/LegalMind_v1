"""Roadmap PHASE 6 — score the structured query plan. Zero Gemini.

    python3 -m tools.eval_query_plan [--db <scratch corpus url>] [--json out.json]

Against labels that already exist, never labels written for this tool:
  * understanding_matrix.json (76) — requested_fact, authority, temporal, jurisdiction
  * rag_benchmark.json (76) — `answer.distinguish` is the set of source kinds an
    answer must keep apart: the plan's lanes are scored against it (recall per lane,
    and the special lanes' false-positive rate on cases that label none of them)
  * convergence — every phrasing that must reach the same topic (roadmap §6's five
    plus the golden early-termination variants)
  * language — category K is romanised Hindi
With --db, a retrieval check: the Constitution and position lanes searched with the raw
question vs with the plan's sub-queries fused by RRF, scored on the PHASE 0 gold.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from legalmind.assist.query import query_plan, understanding
from legalmind.assist.retrieval import calibration
from tools import rag_benchmark as rb

MATRIX = pathlib.Path(__file__).resolve().parents[1] / "tests/assist_eval/understanding_matrix.json"
SPECIAL = (query_plan.USER_ASSERTION, query_plan.MISSING_DOCUMENT,
           query_plan.HISTORICAL_EXCEPTION)
CONVERGE = ("terminate early", "end the MSA early", "exit before the term ends",
            "customer wants to leave early", "agreement ko jaldi end karna hai")
EARLY_EXIT = "Fixed-Term Commitments & Early Exit"


def _frac(xs):
    xs = list(xs)
    return round(sum(xs) / len(xs), 4) if xs else None


def matrix_scores() -> dict:
    items = next(v for v in json.loads(MATRIX.read_text()).values() if isinstance(v, list))
    got = [(i, understanding.understand(i["q"])) for i in items]
    return {
        "n": len(items),
        "requested_fact": _frac(u.requested_fact == i["requested_fact"] for i, u in got),
        "authority_exact": _frac(sorted(u.authority) == sorted(i["authority"])
                                 for i, u in got),
        "temporal": _frac(u.temporal.kind == i["temporal"] for i, u in got
                          if "temporal" in i),
        "jurisdiction": _frac(u.jurisdiction == i["jurisdiction"] for i, u in got
                              if "jurisdiction" in i),
    }


def plan_scores(cases) -> dict:
    lane_hits: dict[str, list[bool]] = {}
    false_special = []
    for c in cases:
        p = query_plan.plan(c["question"] if not c.get("after")
                            else f"{c['after']} {c['question']}", has_document=False)
        want = set(c.get("answer", {}).get("distinguish", []))
        for lane in want:
            lane_hits.setdefault(lane, []).append(lane in p.lanes)
        if not want & set(SPECIAL):
            false_special.append(bool(p.lanes & set(SPECIAL)))
    golden = [query_plan.plan(c["question"]) for c in cases if c.get("golden")]
    return {
        "lane_recall": {k: _frac(v) for k, v in sorted(lane_hits.items())},
        "lane_labels": {k: len(v) for k, v in sorted(lane_hits.items())},
        "special_lane_false_positive_rate": _frac(false_special),
        "convergence_early_exit": _frac(
            query_plan.plan(q).topic == EARLY_EXIT
            for q in (*CONVERGE, *(c["question"] for c in cases
                                   if c.get("golden") and c["id"] != "GT-11"))),
        "language_hinglish_recall": _frac(query_plan.plan(c["question"]).language
                                          == "hinglish" for c in cases
                                          if c["category"] == "K"),
        "language_en_precision": _frac(query_plan.plan(c["question"]).language == "en"
                                       for c in cases if c["category"] != "K"),
        "golden_figures": {c["id"]: list(query_plan.plan(c["question"]).figures)
                           for c in cases if c.get("golden")
                           and query_plan.plan(c["question"]).figures},
        "golden_complex": _frac(p.complex for p in golden),
        "GT-00": _describe(query_plan.plan(next(c for c in cases
                                                 if c["id"] == "GT-00")["question"])),
    }


def _describe(p) -> dict:
    return {"topic": p.topic, "language": p.language, "figures": list(p.figures),
            "claims": len(p.claims), "document_state": p.document_state,
            "lanes": sorted(p.lanes),
            "sub_questions": [{"lanes": list(s.lanes), "query": s.query}
                              for s in p.sub_questions]}


def retrieval_check(db, cases) -> dict:
    """Raw question vs the plan's sub-queries, RRF-fused, same functions and limits."""
    from legalmind.assist.knowledge import constitution, positions

    def fused(search, queries, key):
        score: dict = {}
        for q in queries:
            for rank, h in enumerate(search(q), 1):
                score[key(h)] = score.get(key(h), 0.0) + 1 / (calibration.RRF_K + rank)
        return sorted(score, key=lambda k: -score[k])

    lanes = {
        "CONST": (lambda q: constitution.search(db, query=q, permissions=rb.PERMISSIONS,
                                                limit=10),
                  lambda h: f"CONST:{h.section_path}"),
        "POS": (lambda q: positions.search_positions(db, query=q,
                                                     permissions=rb.PERMISSIONS, limit=10),
                lambda h: f"POS:{h.standard_code}"),
    }
    out = {}
    for kind, (search, key) in lanes.items():
        raw, planned = [], []
        for c in cases:
            slots = [[r for r in s if r.startswith(kind + ":")] for s in c["gold"]]
            slots = [s for s in slots if s]
            if not slots:
                continue
            q = f"{c['after']} {c['question']}" if c.get("after") else c["question"]
            p = query_plan.plan(q)
            queries = [q, *(s.query for s in p.sub_questions if s.query != q)]
            raw_rank = fused(search, [q], key)
            plan_rank = fused(search, queries, key)
            for slot in slots:
                raw.append(rb._rank(slot, raw_rank))
                planned.append(rb._rank(slot, plan_rank))
        out[kind] = {"slots": len(raw),
                     "raw": {"r@3": _frac(r is not None and r <= 3 for r in raw),
                             "mrr": _frac(1 / r if r else 0 for r in raw)},
                     "planned": {"r@3": _frac(r is not None and r <= 3 for r in planned),
                                 "mrr": _frac(1 / r if r else 0 for r in planned)}}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db")
    ap.add_argument("--json")
    args = ap.parse_args()
    cases = json.loads(rb.DATASET.read_text())["cases"]
    report = {"matrix": matrix_scores(), "plan": plan_scores(cases)}
    if args.db:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        db = sessionmaker(bind=create_engine(
            args.db, connect_args={"options": "-c default_transaction_read_only=on"}))()
        report["retrieval"] = retrieval_check(db, cases)
    print(json.dumps(report, indent=1))
    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
