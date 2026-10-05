"""Roadmap PHASE 4 — benchmark the embedding model, then select. Zero Gemini calls.

    python3 -m tools.benchmark_embedders --model minilm|bge-m3|qwen3 \\
        --db <corpus db url> --gate-db <document corpus db url> [--json out.json]

One model per process, so peak memory is that model's own. Every corpus is read over
a READ-ONLY connection and nothing is written to any database: vectors are computed in
memory (and cached under --cache) and ranked by exact cosine, which is what pgvector's
exact scan does in production.

Measured per domain, vector ranking only — the embedder's own contribution; the
lexical half of hybrid retrieval does not depend on the model:

  CONSTITUTION  the knowledge_items children (breadcrumb + text), PHASE 0 CONST slots
  POSITIONS     the active position chunks, PHASE 0 POS slots
  STATUTES      every statute chunk, PHASE 0 STAT slots
  DOCUMENTS     the ratified 77-question set's answerable questions, ranked within
                their own document version (`AM-25` r6 scope), gold by verified anchor

Hits are collapsed to their REF before ranking (a statute section, a Constitution
section, a standard), so recall means "the right source", not "one of its chunks".
Reported: recall@1/@3/@10, MRR, nDCG@5, per domain and per question category, plus
indexing time, query latency and peak RSS — the cost half of roadmap §4's rule.
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import resource
import statistics
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from legalmind.assist.ingestion.onnx_backend import OnnxEmbeddingBackend, model_root
from tools import rag_benchmark as rb
from tools.benchmark_retrieval import _load_eval_dataset, probe_corpus
from tools.verify_assist_quality import DATASET as DOC_DATASET

# name -> (weights directory, pooling, max tokens, query prefix)
CANDIDATES = {
    "minilm": ("sentence-transformers__all-MiniLM-L6-v2/main", "mean", 512, ""),
    "bge-m3": ("BAAI__bge-m3/5617a9f61b028005a4858fdac845db406aefb181", "cls", 1024, ""),
    # Qwen3 is instruction-aware: the query carries a task line, passages do not
    # (the model card's own usage).
    "qwen3": ("onnx-community__Qwen3-Embedding-0.6B-ONNX/"
              "c25a394dd583836952667c12f008335071b3f43d", "last", 1024,
              "Instruct: Given a legal or contractual question, retrieve the passage "
              "that answers it\nQuery:"),
}


def _ro(url):
    return sessionmaker(bind=create_engine(
        url, connect_args={"options": "-c default_transaction_read_only=on"}))()


def corpora(db) -> dict[str, list[tuple[str, str]]]:
    """domain -> [(ref, text)] — the same refs the PHASE 0 benchmark scores."""
    act = rb._act
    return {
        "CONSTITUTION": [(f"CONST:{r[0]}", f"{r[1]}\n{r[2]}") for r in db.execute(text(
            "SELECT i.section_path, i.breadcrumb, i.content FROM assist.knowledge_items i "
            "JOIN assist.knowledge_sources s ON s.id = i.source_id "
            "WHERE s.status = 'CURRENT' AND i.kind = 'PARAGRAPH' "
            "AND i.status <> 'UNRATIFIED' ORDER BY i.ordinal"))],
        "POSITIONS": [(f"POS:{r[0]}", r[1]) for r in db.execute(text(
            "SELECT pc.standard_code, pc.content FROM assist.position_chunks pc "
            "JOIN requirements q ON q.code = pc.standard_code "
            "WHERE q.status::text <> 'DEPRECATED' ORDER BY pc.standard_code"))],
        "STATUTES": [(f"STAT:{act(r[0])}:{r[1]}", r[2]) for r in db.execute(text(
            "SELECT s.official_title, c.section_number, c.content "
            "FROM assist.statute_chunks c JOIN assist.statutes s ON s.id = c.statute_id "
            "WHERE s.status <> 'WITHDRAWN' ORDER BY s.official_title, c.ordinal"))],
    }


def rank_refs(scores, refs) -> list[str]:
    """Distinct refs in descending best-chunk score — "the right source"."""
    order = sorted(range(len(refs)), key=lambda i: -scores[i])
    return list(dict.fromkeys(refs[i] for i in order))


def metrics(ranks: list[int | None]) -> dict:
    n = len(ranks)
    def at(k):
        return round(sum(1 for r in ranks if r and r <= k) / n, 4) if n else None
    return {"n": n, "r@1": at(1), "r@3": at(3), "r@10": at(10), "r@30": at(30),
            "r@50": at(50),
            "mrr": round(sum(1 / r for r in ranks if r) / n, 4) if n else None,
            "ndcg@5": round(sum(1 / math.log2(r + 1) for r in ranks if r and r <= 5) / n, 4)
            if n else None}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, choices=sorted(CANDIDATES))
    ap.add_argument("--db", required=True)
    ap.add_argument("--gate-db", required=True)
    ap.add_argument("--json")
    ap.add_argument("--cache", default=None)
    args = ap.parse_args()
    import numpy as np

    folder, pooling, max_len, prefix = CANDIDATES[args.model]
    started = time.monotonic()
    model = OnnxEmbeddingBackend(model_root() / folder, pooling=pooling, max_length=max_len)
    load_s = time.monotonic() - started
    cache = pathlib.Path(args.cache) if args.cache else None

    def embed(key: str, texts: list[str]):
        """Embedded in blocks, each saved as it completes, so an interrupted run (a
        reboot cost 1.5 h on 2026-09-24) resumes at the first missing block. A block
        records only its text count and rate; the rate × total is the reported cost."""
        if not cache:
            t0 = time.monotonic()
            return np.array(model.embed(texts), dtype="float32"), time.monotonic() - t0
        cache.mkdir(parents=True, exist_ok=True)
        parts, spent, block = [], 0.0, 256
        for n, start in enumerate(range(0, len(texts), block)):
            path = cache / f"{args.model}-{key}-{n:04d}.npz"
            if path.exists():
                saved = np.load(path)
                parts.append(saved["v"])
                spent += float(saved["s"])
                continue
            t0 = time.monotonic()
            vecs = np.array(model.embed(texts[start:start + block]), dtype="float32")
            took = time.monotonic() - t0
            np.savez(path, v=vecs, s=took)
            parts.append(vecs)
            spent += took
            print(f"  {key}: {min(start + block, len(texts))}/{len(texts)} "
                  f"({took:.0f}s)", file=sys.stderr, flush=True)
        return np.concatenate(parts), spent

    report: dict = {"model": args.model, "identity": model.identity,
                    "dimensions": model.dimensions, "load_s": round(load_s, 1),
                    "domains": {}, "categories": {}, "index_s": {}}
    latencies: list[float] = []

    def query_vec(q: str):
        t0 = time.monotonic()
        v = np.array(model.embed([f"{prefix}{q}" if prefix else q])[0], dtype="float32")
        latencies.append((time.monotonic() - t0) * 1000)
        return v

    cases = json.loads(rb.DATASET.read_text())["cases"]
    by_cat: dict[str, list] = {}
    corpus_db = _ro(args.db)
    for domain, rows in corpora(corpus_db).items():
        refs = [r for r, _ in rows]
        vecs, spent = embed(domain, [t for _, t in rows])
        report["index_s"][domain] = {"texts": len(rows), "seconds": round(spent, 1)}
        kind = {"CONSTITUTION": "CONST", "POSITIONS": "POS", "STATUTES": "STAT"}[domain]
        ranks = []
        for c in cases:
            slots = [[r for r in s if r.startswith(kind + ":")] for s in c["gold"]]
            slots = [s for s in slots if s]
            if not slots:
                continue
            q = f"{c['after']} {c['question']}" if c.get("after") else c["question"]
            ranking = rank_refs(vecs @ query_vec(q), refs)
            for slot in slots:
                r = rb._rank(slot, ranking)
                ranks.append(r)
                by_cat.setdefault(c["category"], []).append(r)
        report["domains"][domain] = metrics(ranks)

    # DOCUMENTS — the ratified set, scoped per document version.
    gate = _ro(args.gate_db)
    questions = _load_eval_dataset(DOC_DATASET)
    versions, expected = probe_corpus(gate, questions)
    chunk_rows = {}
    for name, dv in versions.items():
        chunk_rows[name] = [(r[0], r[1]) for r in gate.execute(text(
            "SELECT id, content FROM assist.chunks WHERE document_version_id = :d "
            "ORDER BY ordinal"), {"d": dv})]
    all_texts = [(n, cid, t) for n, rows in chunk_rows.items() for cid, t in rows]
    vecs, spent = embed("DOCUMENTS", [t for _, _, t in all_texts])
    report["index_s"]["DOCUMENTS"] = {"texts": len(all_texts), "seconds": round(spent, 1)}
    doc_ranks: list[int | None] = []
    by_difficulty: dict[str, list[int | None]] = {}
    for q in questions:
        if q["expected"] != "ANSWERABLE" or q["document"] not in versions:
            continue
        idx = [i for i, (n, _, _) in enumerate(all_texts) if n == q["document"]]
        scores = vecs[idx] @ query_vec(q["question"])
        order = [all_texts[idx[i]][1] for i in np.argsort(-scores)]
        gold = expected.get(q["id"], set())
        r = next((i for i, cid in enumerate(order, 1) if cid in gold), None)
        doc_ranks.append(r)
        by_difficulty.setdefault(q["difficulty"], []).append(r)
    report["domains"]["DOCUMENTS"] = metrics(doc_ranks)
    report["categories"] = {k: metrics(v) for k, v in sorted(by_cat.items())}
    report["documents_by_difficulty"] = {k: metrics(v) for k, v in sorted(by_difficulty.items())}
    report["query_ms"] = {"p50": round(statistics.median(latencies), 1),
                          "p95": round(sorted(latencies)[int(len(latencies) * .95)], 1),
                          "n": len(latencies)}
    report["peak_rss_mb"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)
    print(json.dumps(report, indent=1))
    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
