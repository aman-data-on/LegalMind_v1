"""PHASE 8 — the owner's instruction: re-test bge-m3 for STATUTES after reranking.

    python3 -m tools.retest_statute_embedder --db <scratch url> --cache <vector cache>

The embedder is isolated: both arms get the SAME lexical lane (the production statute
search with no vectors) and the SAME cross-encoder rerank (question, top 30, version
before relevance — `retrieval.rerank`'s rule); only the dense lane differs, read from
the PHASE 4 vector cache (`tools/benchmark_embedders.py`). Scored on every PHASE 0
statute gold slot. Zero Gemini, read-only.
"""
from __future__ import annotations

import argparse
import glob
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from legalmind.assist.ingestion.onnx_backend import OnnxEmbeddingBackend, model_root
from legalmind.assist.knowledge import authority, statutes
from legalmind.assist.query import query_plan
from legalmind.assist.retrieval import calibration
from legalmind.assist.retrieval import rerank as cross_encoder
from tools import benchmark_embedders as be
from tools import rag_benchmark as rb


def main() -> int:
    import numpy as np

    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--cache", required=True)
    ap.add_argument("--json")
    args = ap.parse_args()
    db = sessionmaker(bind=create_engine(
        args.db, connect_args={"options": "-c default_transaction_read_only=on"}))()
    rows = be.corpora(db)["STATUTES"]
    refs = [r for r, _ in rows]
    texts = [t for _, t in rows]
    cases = [c for c in json.loads(rb.DATASET.read_text())["cases"]
             if any(r.startswith("STAT:") for s in c["gold"] for r in s)]
    report = {}
    for model in ("minilm", "bge-m3"):
        vecs = np.concatenate([np.load(f)["v"] for f in sorted(
            glob.glob(f"{args.cache}/{model}-STATUTES-*.npz"))])
        assert len(vecs) == len(refs), "the cache does not match this corpus"
        folder, pooling, max_len, prefix = be.CANDIDATES[model]
        emb = OnnxEmbeddingBackend(model_root() / folder, pooling=pooling,
                                   max_length=max_len)
        pre, post = [], []
        for c in cases:
            q = f"{c['after']} {c['question']}" if c.get("after") else c["question"]
            plan = query_plan.plan(q)
            lexical = [f"STAT:{h.official_title.removeprefix('The ')}:{h.section_number}"
                       for h in statutes.search_statutes(
                           db, query=q, permissions=rb.PERMISSIONS, limit=50,
                           embed_query=lambda _q: None, candidates=True)]
            dense_order = np.argsort(-(vecs @ np.array(emb.embed([q])[0])))
            dense = list(dict.fromkeys(refs[i] for i in dense_order))[:50]
            fused: dict[str, float] = {}
            for ranked in (lexical, dense):
                for rank, ref in enumerate(ranked, 1):
                    fused[ref] = fused.get(ref, 0.0) + 1 / (calibration.RRF_K + rank)
            pool = sorted(fused, key=lambda r: -fused[r])
            text_of = {r: texts[refs.index(r)] for r in pool[:30]}
            scores = cross_encoder.scores(q, [text_of[r] for r in pool[:30]]) or []
            head = sorted(pool[:30], key=lambda r: -scores[pool.index(r)]) if scores \
                else pool[:30]
            if not plan.understood.temporal.wants_past:
                head.sort(key=lambda r: authority.of_statute("The " + r[5:])[1]
                          != "CURRENT")
            ranked_after = head + pool[30:]
            for slot in c["gold"]:
                stat = [r for r in slot if r.startswith("STAT:")]
                if stat:
                    pre.append(rb._rank(stat, pool))
                    post.append(rb._rank(stat, ranked_after))
        report[model] = {"slots": len(post), "pool_r@50": _at(pre, 50),
                         "reranked_r@1": _at(post, 1), "reranked_r@3": _at(post, 3),
                         "reranked_r@6": _at(post, 6),
                         "reranked_mrr": round(sum(1 / r for r in post if r)
                                               / len(post), 4)}
        print(model, report[model], flush=True)
    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(report, indent=1))
    return 0


def _at(ranks, k):
    return round(sum(1 for r in ranks if r and r <= k) / len(ranks), 4)


if __name__ == "__main__":
    sys.exit(main())
