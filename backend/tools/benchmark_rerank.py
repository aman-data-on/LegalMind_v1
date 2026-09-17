"""The reranker bakeoff — `AM-26` r2's smallest-that-passes, measured on the ratified set.

    python3 -m tools.benchmark_rerank                 # all provisioned candidates
    python3 -m tools.benchmark_rerank --candidates cross-encoder/ms-marco-MiniLM-L-6-v2

`AM-25`'s permitted list already names "hybrid retrieval with reranking" and `AM-26`'s
stack table already names a "Reranking model | local, self-hosted, open-weight,
cross-encoder", so no amendment is required to MEASURE one — only r2 (smallest upward,
stop at the first that passes), r3 (measured on real supplied material including
questions with no answer), and r4/r5 (pinned, checksummed, never fetched at runtime).

--------------------------------------------------------------------------
What this measures, and what it deliberately does not touch
--------------------------------------------------------------------------
This is an OFFLINE measurement. It calls no generative model, changes no production
behaviour, and writes no baseline. For each ratified question it runs the production
retrieval, takes the candidate list, and asks each cross-encoder to reorder it — then
scores the orderings against the dataset's own `section` anchors.

Two different uses of a reranker are measured SEPARATELY, because they carry different
risk:

    REORDER      the gate's decision is untouched; the reranker only reorders the hits
                 the gate already admitted. This cannot change a refusal into an answer
                 or the reverse, so it cannot move the wrongly-answered rate at all.
                 It can move MRR, gold@3, hit@1 and evidence precision.

    GATE OPENER  a shut gate is reopened when the reranker's top score clears a floor.
                 This CAN change refusals in both directions and therefore needs the
                 separability evidence below before any floor is proposed.

For the gate-opener question the only honest measurement is separability: the top rerank
score on the answerable questions the gate wrongly refuses, against the top rerank score
on the 13 questions that have no answer. If those two distributions overlap, no floor
exists that recovers the false refusals without admitting the unanswerable — which is
exactly what the 2026-09-16 threshold sweep, the IDF feature and the model swap each
found for the similarity features, and why the evidence rescue was built instead.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import statistics
import sys
import time

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from legalmind.assist import embedding_runtime, store
from legalmind.assist.onnx_backend import OnnxCrossEncoderBackend, model_root
from legalmind.ingestion.storage import LocalFilesystemStorage
from tools.benchmark_retrieval import (
    _bench_url,
    _chunks,
    _ingest_corpus,
    _load_eval_dataset,
    _resolve_anchors,
)
from tools.verify_assist_quality import DATASET, _documents

#: How deep a candidate pool this EXPERIMENT gives the reranker. **Production does not
#: use this.** `service.retrieve_document` calls `store.search_hybrid` with no limit, so
#: the shipped pool is `RETRIEVAL_TOP_K` = 10 and truncation happens inside the search,
#: before the reranker is reached — which is what makes the shipped reranker "reorders
#: only, membership unchanged" rather than a retrieval change wearing a ranking label.
#:
#: 30 is set here deliberately, to test whether a DEEPER pool would let reranking pull a
#: gold chunk up into the top 10. Measured 2026-09-17: it would not. Of 77 ratified
#: questions exactly ONE had the gate open with its gold chunk ranked 11-30, so the
#: deeper pool buys a single question — while 20 had the gold chunk present with the gate
#: SHUT, which no amount of reordering reaches. The pool was widened, measured, and
#: rejected on that evidence; do not read this constant as what production does.
RERANK_CANDIDATES = 30
TOP_K = 10


def _provisioned() -> list[pathlib.Path]:
    """Every provisioned cross-encoder, smallest weights first — `AM-26` r2's order."""
    roots = [d for d in model_root().glob("cross-encoder__*/*")
             if (d / "manifest.json").exists()]
    return sorted(roots, key=lambda d: (d / "model.onnx").stat().st_size)


def _candidates(db, question: str, document_version_id) -> list:
    """The production retrieval, with the gate's own decision recorded alongside.

    `search_hybrid` returns [] for `hits` when the gate is shut and carries the sub-gate
    rows in `candidates` — so both paths give a pool to rerank, and the gate's verdict is
    preserved rather than bypassed.
    """
    outcome = store.search_hybrid(
        db, document_version_id=document_version_id, query=question,
        embed_query=embedding_runtime.embed_query, limit=RERANK_CANDIDATES)
    pool = outcome.hits if outcome.gate_open else outcome.candidates
    return outcome, pool


def _rank_of_gold(ordered_ids: list, gold: set) -> int | None:
    for i, cid in enumerate(ordered_ids, start=1):
        if cid in gold:
            return i
    return None


def measure(db, versions: dict, all_chunks: dict, questions: list[dict],
            backend: OnnxCrossEncoderBackend | None) -> dict:
    """Score one ordering — the retrieval's own when `backend` is None, else reranked."""
    expected, failures = _resolve_anchors(questions, all_chunks)
    if failures:
        raise SystemExit("anchor resolution failed:\n  " + "\n  ".join(failures))

    answerable = hits10 = hits3 = hits1 = retained = 0
    mrr_sum = precision_sum = 0.0
    latencies: list[float] = []
    # Separability: the reranker's TOP score, split by what the question actually is.
    top_false_refusal: list[float] = []      # answerable, gate shut, gold in the pool
    top_true_miss: list[float] = []          # answerable, gate shut, gold NOT in the pool
    top_unanswerable: list[float] = []       # the 13 with no answer anywhere
    top_answered: list[float] = []           # gate already open

    for q in questions:
        outcome, pool = _candidates(db, q["question"], versions[q["document"]])
        texts = [h.content for h in pool]
        if backend is not None and texts:
            started = time.monotonic()
            scores = backend.score(q["question"], texts)
            latencies.append((time.monotonic() - started) * 1000)
            order = sorted(range(len(pool)), key=lambda i: scores[i], reverse=True)
            ordered = [pool[i] for i in order][:TOP_K]
            top_score = max(scores)
        else:
            ordered = pool[:TOP_K]
            top_score = None

        gold = expected.get(q["id"], set())
        ids = [h.chunk_id for h in ordered]

        if q["expected"] == "NOT_FOUND":
            if top_score is not None:
                top_unanswerable.append(top_score)
            continue

        answerable += 1
        if not outcome.gate_open:
            # A refusal the reranker did not change — it only reorders here.
            if top_score is not None:
                (top_false_refusal if _rank_of_gold([h.chunk_id for h in pool], gold)
                 else top_true_miss).append(top_score)
            continue
        if top_score is not None:
            top_answered.append(top_score)
        retained += 1
        rank = _rank_of_gold(ids, gold)
        if rank:
            hits10 += 1
            mrr_sum += 1.0 / rank
            if rank <= 3:
                hits3 += 1
            if rank == 1:
                hits1 += 1
        if ids:
            precision_sum += len([c for c in ids if c in gold]) / len(ids)

    def pct(values: list[float], q: float) -> float | None:
        if not values:
            return None
        ordered_v = sorted(values)
        return round(ordered_v[min(len(ordered_v) - 1, round(q * (len(ordered_v) - 1)))], 1)

    return {
        "answerable": answerable, "retained": retained,
        "recall_at_10": round(hits10 / answerable, 3) if answerable else None,
        "mrr": round(mrr_sum / answerable, 3) if answerable else None,
        "gold_in_top_3": round(hits3 / answerable, 3) if answerable else None,
        "hit_at_1": round(hits1 / answerable, 3) if answerable else None,
        "evidence_precision": round(precision_sum / retained, 3) if retained else None,
        "rerank_ms_p50": pct(latencies, 0.50), "rerank_ms_p95": pct(latencies, 0.95),
        "separability": {
            "false_refusal": _describe(top_false_refusal),
            "true_miss": _describe(top_true_miss),
            "unanswerable": _describe(top_unanswerable),
            "answered": _describe(top_answered),
        },
    }


def _describe(values: list[float]) -> dict:
    if not values:
        return {"n": 0}
    return {"n": len(values), "min": round(min(values), 2),
            "median": round(statistics.median(values), 2),
            "max": round(max(values), 2)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--candidates", default="",
                    help="comma-separated repo names; default every provisioned one")
    ap.add_argument("--json", default=None, help="write the full result here")
    args = ap.parse_args(argv)

    if not embedding_runtime.available():
        print("FAIL  the calibrated embedding model is not provisioned; retrieval "
              "would degrade to lexical-only and the pools would not be the shipped "
              "ones. Run tools/provision_model.py first.")
        return 1

    roots = _provisioned()
    if args.candidates:
        wanted = {c.strip().replace("/", "__") for c in args.candidates.split(",")}
        roots = [r for r in roots if r.parent.name in wanted]
    if not roots:
        print("FAIL  no provisioned cross-encoder found under "
              f"{model_root()}. Provision one with tools/provision_model.py.")
        return 1

    questions = _load_eval_dataset(DATASET)
    print(f"Reranker bakeoff — {len(questions)} ratified questions, "
          f"pool of {RERANK_CANDIDATES}, top-{TOP_K} scored\n")

    engine = create_engine(_bench_url(), future=True)
    db = sessionmaker(bind=engine, future=True)()
    storage = LocalFilesystemStorage(".e2e/rerank-bakeoff-objects")
    results: dict[str, dict] = {}
    try:
        versions = _ingest_corpus(db, storage, _documents(questions))
        all_chunks = {name: _chunks(db, dv) for name, dv in versions.items()}
        db.commit()
        results["BASELINE (no reranker)"] = measure(db, versions, all_chunks,
                                                    questions, None)
        for root in roots:
            backend = OnnxCrossEncoderBackend(root)
            size_mb = round((root / "model.onnx").stat().st_size / 1e6)
            label = f"{backend.identity}  ({size_mb} MB)"
            print(f"  scoring {label} …", flush=True)
            results[label] = measure(db, versions, all_chunks, questions, backend)
    finally:
        db.rollback(); db.close(); engine.dispose()

    print(f"\n{'ordering':58} {'recall':>7} {'MRR':>6} {'gold@3':>7} "
          f"{'hit@1':>6} {'ev.prec':>8} {'ms p50/p95':>12}")
    for label, m in results.items():
        ms = (f"{m['rerank_ms_p50']}/{m['rerank_ms_p95']}"
              if m["rerank_ms_p50"] is not None else "—")
        print(f"{label:58} {m['recall_at_10']:>7} {m['mrr']:>6} "
              f"{m['gold_in_top_3']:>7} {m['hit_at_1']:>6} "
              f"{m['evidence_precision']:>8} {ms:>12}")

    print("\nSEPARABILITY — the reranker's TOP score by what the question actually is.")
    print("A floor can only reopen a shut gate safely if 'false refusal' sits ABOVE")
    print("'unanswerable' with no overlap.\n")
    for label, m in results.items():
        if m["rerank_ms_p50"] is None:
            continue
        print(f"  {label}")
        for group in ("false_refusal", "true_miss", "unanswerable", "answered"):
            d = m["separability"][group]
            if d["n"]:
                print(f"    {group:14} n={d['n']:2d}  min {d['min']:>7}  "
                      f"median {d['median']:>7}  max {d['max']:>7}")
            else:
                print(f"    {group:14} n= 0")
        print()

    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(results, indent=1) + "\n")
        print(f"written {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
