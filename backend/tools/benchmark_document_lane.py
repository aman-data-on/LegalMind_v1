"""The document lane of the multi-source Ask path, measured — zero Gemini.

The multi-source path was validated on no-document questions only (`AM-94`: "`on` —
the document lane has no benchmark"). This runs the owner-ratified document questions
(`tests/assist_eval/questions_draft.json`, CONTRACT category) through the path a
document conversation takes — routing with the document in scope, the query plan,
the candidate pool (the document's own chunks beside the Constitution, positions and
statutes), the rerank, the evidence bundle — and scores whether the document's gold
chunk reaches the evidence shown, and whether a NOT_FOUND question gets document text
admitted as its answer.

The documents are ingested through the REAL pipeline (`ingest_document` →
`index_document_version`, the Tier-2 gate's own helpers) into the database given by
``--db``, which must be a scratch copy: this tool WRITES documents into it.

Usage: python3 -m tools.benchmark_document_lane --db <scratch url> [--json out.json]
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

from legalmind import config
from legalmind.assist import evidence, query_plan, retrieval, routing, statutes
from legalmind.ingestion.storage import LocalFilesystemStorage
from tools.benchmark_retrieval import (
    _chunks,
    _ingest_corpus,
    _load_eval_dataset,
    _resolve_anchors,
)
from tools.rag_benchmark import PERMISSIONS

DATASET = pathlib.Path(__file__).resolve().parents[1] / "tests" / "assist_eval" \
    / "questions_draft.json"


def document_case(db, question: str, document_version_id) -> dict:
    """One question with its document in scope, through the multi-source stages."""
    route = routing.plan(question, has_document=True, permissions=PERMISSIONS,
                         statutes_available=statutes.available(db),
                         statute_jurisdictions=statutes.jurisdictions(db))
    if route.general_knowledge or route.capability or route.comparison or route.unmet:
        return {"screen": "comparison" if route.comparison else "other"}
    plan = query_plan.plan(question, has_document=True)
    t = time.perf_counter()
    pool = retrieval.rerank(retrieval.candidates(
        db, plan, route, permissions=PERMISSIONS,
        document_version_id=document_version_id), plan)
    bundle = evidence.build(db, plan, pool, retrieval.select(pool, plan))
    return {"screen": None, "ms": round((time.perf_counter() - t) * 1000),
            "answerable": bundle.answerable,
            "shown": [s.ref for s in bundle.shown()],
            "doc_units": [(s.ref, s.reason) for s in bundle.sources
                          if s.ref.startswith("DOC:")],
            "document_gate": pool.document_gate}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True, help="a SCRATCH database (documents are written)")
    ap.add_argument("--json")
    args = ap.parse_args(argv)
    questions = [q for q in _load_eval_dataset(DATASET) if q["category"] == "CONTRACT"]
    source = pathlib.Path(config.source_material_dir())
    docs = sorted({q["document"] for q in questions})
    db = sessionmaker(bind=create_engine(args.db, future=True), future=True)()
    storage = LocalFilesystemStorage(".e2e/document-lane-objects")
    versions = _ingest_corpus(db, storage, [source / d for d in docs])
    db.commit()
    missing = set(docs) - set(versions)
    if missing:
        raise SystemExit(f"could not ingest: {sorted(missing)}")
    expected, failures = _resolve_anchors(
        questions, {d: _chunks(db, v) for d, v in versions.items()})
    if failures:
        raise SystemExit("anchor resolution failed:\n  " + "\n  ".join(failures))

    rows = []
    for q in questions:
        out = document_case(db, q["question"], versions[q["document"]])
        gold = {f"DOC:{cid}" for cid in expected.get(q["id"], set())}
        shown = out.get("shown", [])
        rank = next((i for i, r in enumerate(shown, 1) if r in gold), None)
        rows.append({"id": q["id"], "expected": q["expected"], "document": q["document"],
                     "gold_rank": rank, **out,
                     "doc_admitted": [r for r in shown if r.startswith("DOC:")]})
    db.rollback()

    answerable = [r for r in rows if r["expected"] == "ANSWERABLE"]
    not_found = [r for r in rows if r["expected"] == "NOT_FOUND"]
    scored = [r for r in answerable if r["screen"] is None]
    summary = {
        "answerable": len(answerable),
        "screened": sum(r["screen"] is not None for r in answerable),
        "gold_shown": sum(r["gold_rank"] is not None for r in scored),
        "gold_at_3": sum(bool(r["gold_rank"] and r["gold_rank"] <= 3) for r in scored),
        "bundle_answerable": sum(bool(r.get("answerable")) for r in scored),
        "not_found": len(not_found),
        "not_found_doc_admitted": [r["id"] for r in not_found if r.get("doc_admitted")],
        "missed": [r["id"] for r in scored if r["gold_rank"] is None],
        "bundle_ms_p50": statistics.median([r["ms"] for r in rows if "ms" in r] or [0]),
    }
    print(json.dumps(summary, indent=1))
    if args.json:
        pathlib.Path(args.json).write_text(json.dumps({"summary": summary, "rows": rows},
                                                      indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
