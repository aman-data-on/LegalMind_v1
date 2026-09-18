"""Deterministic targeting probe — the gate removed from the measurement.

Run it against a gate database that already holds an ingested corpus (the
Tier-2 gate leaves one behind):

    LEGALMIND_QUERY_PLANNER=on python3 tools/probe_targeting.py

It prints planner OFF / aiming only / aiming + widening side by side over the
same anchors, and the three rows are directly comparable because nothing in
the path is nondeterministic.

The Tier-2 gate scores recall@10/hit@1/MRR/precision ONLY over questions whose
gate opened, and gate opening runs through the rescue judge -- a provider call.
So its targeting numbers move run to run for reasons that have nothing to do
with retrieval, which is exactly what three planner runs showed.

This scores the SAME anchors over `store.search_hybrid` output directly, for
every answerable question, with no gate, no rescue and no generation. Nothing
in this path calls a provider, so a difference here IS the mechanism.
"""
import os
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
os.environ.setdefault("LEGALMIND_SOURCE_MATERIAL_DIR", "/root/Legalmind.v1/legal-docs")
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from legalmind.assist import embedding_runtime, planner, store
from tools.benchmark_retrieval import _load_eval_dataset, probe_corpus
from tools.verify_assist_quality import DATASET, _gate_url


def score(db, vmap, expected, questions, *, use_plan, expand):
    hits1 = hits10 = hits3 = n = 0
    mrr = prec = 0.0
    planned = 0
    for q in questions:
        if q["expected"] == "NOT_FOUND" or q["document"] not in vmap:
            continue
        plan = planner.plan_lexical(q["question"]) if use_plan else None
        if plan:
            planned += 1
        extra = tuple(plan.queries) if (plan and expand) else ()
        out = store.search_hybrid(
            db, document_version_id=vmap[q["document"]], query=q["question"],
            embed_query=embedding_runtime.embed_query, extra_queries=extra)
        ranked = [h.chunk_id for h in out.hits]
        exp = expected.get(q["id"], set())
        n += 1
        if not ranked:
            continue
        gold = [i for i, c in enumerate(ranked, 1) if c in exp]
        if gold:
            hits10 += 1
            mrr += 1.0 / gold[0]
            if gold[0] <= 3:
                hits3 += 1
        if ranked[0] in exp:
            hits1 += 1
        prec += len(gold) / len(ranked)
    return {"n": n, "planned": planned, "recall@10": round(hits10 / n, 4),
            "hit@1": round(hits1 / n, 4), "mrr": round(mrr / n, 4),
            "gold@3": round(hits3 / n, 4), "precision": round(prec / n, 4)}


def main():
    qs = _load_eval_dataset(DATASET)
    db = sessionmaker(bind=create_engine(_gate_url(), future=True), future=True)()
    vmap, expected = probe_corpus(db, qs)
    print(f"corpus: {len(vmap)} document versions, anchors for {len(expected)} questions\n")
    runs = (("planner OFF (production)", False, False),
            ("planner ON, aiming only", True, False),
            ("planner ON, aiming + widening", True, True))
    for label, use_plan, expand in runs:
        m = score(db, vmap, expected, qs, use_plan=use_plan, expand=expand)
        print(f"{label:32} n={m['n']} planned={m['planned']:2}  "
              f"recall@10={m['recall@10']}  hit@1={m['hit@1']}  "
              f"mrr={m['mrr']}  gold@3={m['gold@3']}  precision={m['precision']}")


main()
