"""Answer focus — which evidence becomes the answer's claims, scored with ZERO Gemini.

    python3 -m tools.benchmark_answer_focus --db <url> [--json out.json]

`tools.rag_benchmark` scores what the evidence bundle SHOWS; this scores the step after
it — `contracts.build`, the approved claims Gemini is allowed to say — over every
answerable golden-benchmark case (`tests/assist_eval/rag_benchmark.json`). Per case:

  primary_gold   the first claim comes from the question's first gold slot
  slots_claimed  gold slots with at least one claim (the answer can still say each part)
  off_gold       claims from a source no gold slot names — what crowds the answer
  must_not       claims from a `must_not` source
  claims         how many claims the model is given

The connection is READ ONLY, so it may point at the production database.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import statistics
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from legalmind.assist.synthesis import contracts
from tools.rag_benchmark import DATASET, bundle_for, ref_matches


def score(case: dict, claim_refs: list[str]) -> dict:
    slots = case["gold"]
    gold_refs = [r for slot in slots for r in slot]
    return {
        "id": case["id"], "claims": len(claim_refs),
        "primary_gold": bool(claim_refs and slots
                             and any(ref_matches(r, claim_refs[0]) for r in slots[0])),
        "slots_claimed": sum(any(ref_matches(r, c) for r in slot for c in claim_refs)
                             for slot in slots),
        "slots": len(slots),
        "off_gold": sum(not any(ref_matches(r, c) for r in gold_refs) for c in claim_refs),
        "must_not": sum(any(ref_matches(r, c) for r in case["must_not"])
                        for c in claim_refs),
        "claim_refs": claim_refs,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True)
    ap.add_argument("--json")
    args = ap.parse_args()
    engine = create_engine(args.db, future=True,
                           connect_args={"options": "-c default_transaction_read_only=on"})
    db = sessionmaker(bind=engine, future=True)()
    cases = [c for c in json.loads(pathlib.Path(DATASET).read_text())["cases"]
             if c["gold"] and not c.get("answer", {}).get("refuse")]
    rows = []
    for case in cases:
        built = bundle_for(db, case)
        if built is None or not built[1].answerable:
            continue
        plan, bundle = built
        row = score(case, [c.ref for c in contracts.build(bundle, case["question"], db)])
        gold = [r for slot in case["gold"] for r in slot]
        wanted = contracts.question_families(case["question"])
        row["sources"] = [[s.ref, s.kind, round(s.relevance or 0, 2),
                           any(ref_matches(r, s.ref) for r in gold),
                           not (f := contracts.source_families(s)) or bool(f & wanted)]
                          for s in bundle.shown()]
        row["lanes"] = sorted(plan.lanes)
        rows.append(row)
    db.rollback()
    n = len(rows)
    summary = {
        "cases": n,
        "primary_gold": sum(r["primary_gold"] for r in rows),
        "slots_claimed": f'{sum(r["slots_claimed"] for r in rows)}/'
                         f'{sum(r["slots"] for r in rows)}',
        "off_gold_claims": sum(r["off_gold"] for r in rows),
        "must_not_claims": sum(r["must_not"] for r in rows),
        "claims_mean": round(statistics.mean(r["claims"] for r in rows), 2) if n else 0,
        "gemini_calls": 0,
    }
    print(json.dumps(summary, indent=1))
    if args.json:
        pathlib.Path(args.json).write_text(json.dumps({"summary": summary, "rows": rows},
                                                      indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
