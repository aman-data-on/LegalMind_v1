"""Why each answerable question of the frozen set misses — charter backlog item 4, Phase 3 A4.

    python3 -m tools.classify_misses --db <url with the 15 supplied documents ingested>

Zero Gemini. Scores every ANSWERABLE question of q77-v1 exactly as the earlier probe
does (`probe_targeting`: the gated `store.search_hybrid` top 10, gold = chunks holding
the question's ratified anchor) and gives each miss ONE cause, first that applies:

    ANCHOR_SPLIT    the anchor is in no chunk but spans two adjacent chunks
    ANCHOR_LOST     the anchor is in no chunk at all
    GATE_CLOSED     gold is in the question's own top 10, but the calibrated gate shut
                    (a calibration matter — never changed without a decision)
    RANK_CUTOFF     the gate opened; gold is in the 50-deep pool, below rank 10
    RETRIEVAL_MISS  gold is not in the pool

Read-only. Prints question ids, documents (the supplied source files), ranks and gate
signals — no document text.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from itertools import pairwise

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from legalmind.assist import embedding_runtime, store
from tools.benchmark_retrieval import _chunks, _load_eval_dataset, _normalize_ws
from tools.verify_assist_quality import DATASET

POOL = 50


def classify(db, questions, *, tool_path: bool = False) -> list[dict]:
    """`tool_path`: rank as the Phase 3 tool does — the top 10 candidates whatever the
    gate decided (`tools._documents`, A-31) — instead of the current pipeline's gated
    hits. The gate's decision is still recorded."""
    versions: dict = {}
    for name, dv in db.execute(text("SELECT original_filename, id FROM document_versions "
                                    "ORDER BY created_at DESC")).all():
        versions.setdefault(name, dv)
    out = []
    for q in questions:
        if q["expected"] != "ANSWERABLE" or q["document"] not in versions:
            continue
        dv = versions[q["document"]]
        chunks = _chunks(db, dv)
        needle = _normalize_ws(q["anchor"])
        gold = {cid for cid, c in chunks if needle in _normalize_ws(c)}
        gated = store.search_hybrid(db, document_version_id=dv, query=q["question"],
                                    embed_query=embedding_runtime.embed_query)
        pool = store.search_hybrid(db, document_version_id=dv, query=q["question"],
                                   embed_query=embedding_runtime.embed_query, limit=POOL,
                                   candidates=True)
        pool_ids = [h.chunk_id for h in pool.hits]
        ranked = pool_ids[:10] if tool_path else [h.chunk_id for h in gated.hits]
        rank = next((i for i, c in enumerate(ranked, 1) if c in gold), None)
        pool_rank = next((i for i, c in enumerate(pool_ids, 1) if c in gold), None)
        if rank:
            cause = None
        elif not gold:
            cause = ("ANCHOR_SPLIT" if any(needle in _normalize_ws(a + " " + b)
                                           for (_, a), (_, b) in pairwise(chunks))
                     else "ANCHOR_LOST")
        elif not gated.gate_open and pool_rank and pool_rank <= 10:
            cause = "GATE_CLOSED"
        elif pool_rank:
            cause = "RANK_CUTOFF"
        else:
            cause = "RETRIEVAL_MISS"
        out.append({"id": q["id"], "document": q["document"], "rank": rank,
                    "pool_rank": pool_rank, "cause": cause, "gate_open": gated.gate_open,
                    "lexical_hit": gated.lexical_hit,
                    "top": round(gated.vector_top_score or 0, 3),
                    "gap": round(gated.vector_peak_gap or 0, 3)})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--json")
    ap.add_argument("--tool-path", action="store_true",
                    help="rank as the Phase 3 tool does (candidates, gate as a signal)")
    args = ap.parse_args()
    db = sessionmaker(bind=create_engine(args.db, future=True), future=True)()
    rows = classify(db, _load_eval_dataset(DATASET), tool_path=args.tool_path)
    db.rollback()
    misses = [r for r in rows if r["cause"]]
    n = len(rows)
    print(f"answerable {n}  hits@10 {n - len(misses)}  recall@10 "
          f"{round((n - len(misses)) / (n or 1), 4)}")
    for cause, k in Counter(r["cause"] for r in misses).most_common():
        ids = [r["id"] for r in misses if r["cause"] == cause]
        print(f"  {cause:15} {k:3}  {', '.join(ids)}")
    if args.json:
        with open(args.json, "w") as f:
            json.dump(rows, f, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
