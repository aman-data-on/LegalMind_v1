"""Roadmap PHASE 5 — measure Postgres + pgvector at the PHASE 7–8 candidate depths.

    python3 -m tools.benchmark_storage --db <corpus url> --gate-db <documents url>
                                       [--json out.json] [--scale 10 40]

Zero Gemini. Query vectors are embedded ONCE up front (MiniLM, the production model) so
every timing below is the database and the retrieval code — never the model.

  1. exact vector KNN per domain at k = 10/30/50/100: p50/p95 latency
  2. exact-search ground truth: pgvector's exact scan equals an independent numpy
     cosine ranking over the same stored vectors (the baseline any ANN is scored on)
  3. lexical (FTS) and metadata-filtered queries at the same depths
  4. the production hybrid functions at depth 50 (lexical + vector + metadata + RRF)
  5. concurrency: 1/4/8/16 parallel clients — throughput and p95
  6. storage and memory: relation sizes, Postgres backend RSS under load
  7. growth: exact scan over the statute vectors replicated ×N in a TEMP table
     (session-scoped, nothing persists) — where exact search would stop being enough

Every connection is READ ONLY except the one that owns the TEMP table in step 7.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import pathlib
import statistics
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from legalmind.assist.ingestion import embedding_runtime
from legalmind.assist.knowledge import constitution, positions, statutes, store
from tools import rag_benchmark as rb
from tools.benchmark_retrieval import _load_eval_dataset, probe_corpus
from tools.verify_assist_quality import DATASET as DOC_DATASET

DEPTHS = (10, 30, 50, 100)
RO = {"options": "-c default_transaction_read_only=on"}


def _stats(ms: list[float]) -> dict:
    ms = sorted(ms)
    return {"n": len(ms), "p50": round(statistics.median(ms), 2),
            "p95": round(ms[min(len(ms) - 1, int(len(ms) * .95))], 2),
            "max": round(ms[-1], 2)}


def _timed(fn) -> float:
    t0 = time.perf_counter()
    fn()
    return (time.perf_counter() - t0) * 1000


def _lit(v) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


VECTOR_SQL = {
    "STATUTES": ("assist.statute_chunk_embeddings", "", ""),
    "POSITIONS": ("assist.position_chunk_embeddings", "", ""),
    "CONSTITUTION": ("assist.knowledge_item_embeddings", "", ""),
    "DOCUMENTS": ("assist.chunk_embeddings e JOIN assist.chunks c ON c.id = e.chunk_id",
                  "WHERE c.document_version_id = :dv", "e."),
}


def knn(db, domain, vec, k, dv=None):
    table, where, alias = VECTOR_SQL[domain]
    op = f'OPERATOR("{store.vector_schema(db)}".<=>)'
    ids = db.execute(text(
        f"SELECT {alias or ''}id FROM {table} {where} "
        f"ORDER BY {alias}embedding {op} CAST(:q AS {store.vector_type(db)}) LIMIT :k"),
        {"q": _lit(vec), "k": k, "dv": dv}).scalars().all()
    return list(ids)


def use(db):
    """`store` caches the pgvector schema per PROCESS (one database in production);
    the two scratch databases install it in different schemas, so switch explicitly."""
    store._VECTOR_SCHEMA = None
    store.vector_schema(db)
    return db


def pg_rss_mb() -> int:
    out = subprocess.run(["ps", "-C", "postgres", "-o", "rss="], capture_output=True,
                         text=True).stdout.split()
    return round(sum(int(x) for x in out) / 1024)


def main() -> int:
    import numpy as np

    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--gate-db", required=True)
    ap.add_argument("--json")
    ap.add_argument("--scale", nargs="*", type=int, default=[10, 40])
    args = ap.parse_args()
    eng = create_engine(args.db, connect_args=RO, pool_size=20)
    geng = create_engine(args.gate_db, connect_args=RO, pool_size=20)
    db, gdb = sessionmaker(bind=eng)(), sessionmaker(bind=geng)()
    report: dict = {"host_cpus": __import__("os").cpu_count()}

    cases = json.loads(rb.DATASET.read_text())["cases"]
    questions = [c["question"] for c in cases]
    doc_qs = [q for q in _load_eval_dataset(DOC_DATASET) if q["expected"] == "ANSWERABLE"]
    versions, _ = probe_corpus(gdb, _load_eval_dataset(DOC_DATASET))
    doc_qs = [q for q in doc_qs if q["document"] in versions]
    qvec = {q: embedding_runtime.embed_query(q)[0] for q in questions}
    dvec = {q["id"]: embedding_runtime.embed_query(q["question"])[0] for q in doc_qs}

    # 1 + 2 — exact KNN latency, and exact == numpy ground truth
    report["vector_knn_ms"], report["exact_ground_truth"] = {}, {}
    for domain in VECTOR_SQL:
        s, qs = (use(gdb), doc_qs) if domain == "DOCUMENTS" else (use(db), questions)
        table, where, alias = VECTOR_SQL[domain]
        report["vector_knn_ms"][domain] = {}
        docs = domain == "DOCUMENTS"
        for k in DEPTHS:
            ms = []
            for q in qs:
                vec, dv = (dvec[q["id"]], versions[q["document"]]) if docs else (qvec[q], None)
                t0 = time.perf_counter()
                knn(s, domain, vec, k, dv)
                ms.append((time.perf_counter() - t0) * 1000)
            report["vector_knn_ms"][domain][k] = _stats(ms)
        if domain != "DOCUMENTS":
            rows = s.execute(text(f"SELECT id, embedding::text FROM {table}")).all()
            ids = [r[0] for r in rows]
            mat = np.array([json.loads(r[1]) for r in rows], dtype="float32")
            agree = []
            for q in qs[:40]:
                truth = [ids[i] for i in np.argsort(-(mat @ np.array(qvec[q])))[:50]]
                got = knn(s, domain, qvec[q], 50)
                agree.append(len(set(truth) & set(got)) / max(1, len(truth)))
            report["exact_ground_truth"][domain] = round(sum(agree) / len(agree), 4)

    # 3 — lexical and metadata-filtered queries at depth
    tsq = "to_tsquery('english', (SELECT array_to_string(tsvector_to_array(" \
          "to_tsvector('english', :q)), ' | ')))"
    lexical = {
        "statutes_fts": f"SELECT id FROM assist.statute_chunks WHERE content_tsv @@ {tsq} "
                        f"ORDER BY ts_rank(content_tsv, {tsq}) DESC LIMIT :k",
        "statutes_fts_current_only": (
            "SELECT c.id FROM assist.statute_chunks c JOIN assist.statutes s "
            f"ON s.id = c.statute_id WHERE s.status = 'CURRENT' AND c.content_tsv @@ {tsq} "
            f"ORDER BY ts_rank(c.content_tsv, {tsq}) DESC LIMIT :k"),
        "statute_exact_reference": (
            "SELECT c.id FROM assist.statute_chunks c JOIN assist.statutes s "
            "ON s.id = c.statute_id WHERE s.official_title LIKE 'The Indian Contract Act%' "
            "AND c.section_number = '74' LIMIT :k"),
        "constitution_fts_current": (
            "SELECT i.id FROM assist.knowledge_items i JOIN assist.knowledge_sources s "
            "ON s.id = i.source_id WHERE s.status = 'CURRENT' AND i.kind = 'PARAGRAPH' "
            f"AND i.status <> 'UNRATIFIED' AND i.content_tsv @@ {tsq} "
            f"ORDER BY ts_rank(i.content_tsv, {tsq}, 1) DESC LIMIT :k"),
        "positions_topic_filter": (
            "SELECT pc.id FROM assist.position_chunks pc JOIN company_standard_versions v "
            "ON v.id = pc.standard_version_id WHERE v.configuration->'constitution'->>"
            "'topic' = 'Termination & Suspension' ORDER BY pc.standard_code LIMIT :k"),
    }
    report["lexical_metadata_ms"] = {
        name: _stats([_timed(lambda q=q, sql=sql: db.execute(text(sql), {"q": q, "k": 50})
                             .all()) for q in questions])
        for name, sql in lexical.items()}

    # 4 — the production hybrid functions at depth 50 (model excluded)
    perms = rb.PERMISSIONS
    use(db)
    report["hybrid_depth50_ms"] = {
        "statutes": _stats([_timed(lambda q=q: statutes.search_statutes(
            db, query=q, permissions=perms, limit=50, embed_query=lambda _q, q=q:
            (qvec[q], "m"))) for q in questions]),
        "positions": _stats([_timed(lambda q=q: positions.search_positions(
            db, query=q, permissions=perms, limit=50, embed_query=lambda _q, q=q:
            (qvec[q], "m"))) for q in questions]),
        "constitution": _stats([_timed(lambda q=q: constitution.search(
            db, query=q, permissions=perms, limit=50, embed_query=lambda _q, q=q:
            (qvec[q], "m"))) for q in questions]),
        "documents": _stats([_timed(lambda q=q: use(gdb) and store.search_hybrid(
            gdb, document_version_id=versions[q["document"]], query=q["question"],
            limit=50, embed_query=lambda _q, q=q: (dvec[q["id"]], "m")))
            for q in doc_qs]),
    }

    # 4b — coexistence: lexical (GIN FTS) + dense (pgvector) + metadata (status) +
    # exact reference (section) fused by RRF in ONE statement and ONE plan
    use(db)
    op = f'OPERATOR("{store.vector_schema(db)}".<=>)'
    vt = store.vector_type(db)
    lanes_sql = f"""
      WITH lex AS (SELECT c.id, row_number() OVER (ORDER BY ts_rank(c.content_tsv, {tsq})
                          DESC) AS r
                     FROM assist.statute_chunks c JOIN assist.statutes s ON s.id = c.statute_id
                    WHERE s.status = 'CURRENT' AND c.content_tsv @@ {tsq} LIMIT 50),
           vec AS (SELECT c.id, row_number() OVER (ORDER BY e.embedding {op}
                          CAST(:v AS {vt})) AS r
                     FROM assist.statute_chunk_embeddings e
                     JOIN assist.statute_chunks c ON c.id = e.statute_chunk_id
                     JOIN assist.statutes s ON s.id = c.statute_id
                    WHERE s.status = 'CURRENT'
                    ORDER BY e.embedding {op} CAST(:v AS {vt}) LIMIT 50),
           ref AS (SELECT c.id, 1 AS r FROM assist.statute_chunks c
                    WHERE c.section_number = ANY(:sec) LIMIT 10)"""
    one_plan = lanes_sql + """
      SELECT id, sum(1.0 / (60 + r)) AS score FROM
        (SELECT * FROM lex UNION ALL SELECT * FROM vec UNION ALL SELECT * FROM ref) u
      GROUP BY id ORDER BY score DESC LIMIT 50"""
    ms, lanes = [], {"lex": 0, "vec": 0, "ref": 0}
    for q in questions:
        sec = [m.group("num").upper() for m in statutes._SECTION_IN_QUESTION.finditer(q)]
        params = {"q": q, "v": _lit(qvec[q]), "sec": sec or [""]}
        ms.append(_timed(lambda p=params: db.execute(text(one_plan), p).all()))
        for lane in lanes:
            lanes[lane] += bool(db.execute(
                text(lanes_sql + f" SELECT count(*) FROM {lane}"), params).scalar())
    report["coexistence_one_plan_ms"] = {**_stats(ms), "questions_with_lane": lanes}

    # 5 + 6 — concurrency and memory under load (statute KNN k=50, the largest scan)
    def one(q):
        with eng.connect() as c:
            s = sessionmaker(bind=c)()
            return _timed(lambda: knn(s, "STATUTES", qvec[q], 50))
    use(db)
    report["concurrency_statutes_k50"] = {}
    rss_idle = pg_rss_mb()
    for clients in (1, 4, 8, 16):
        work = questions * 2
        t0 = time.perf_counter()
        with cf.ThreadPoolExecutor(clients) as pool:
            ms = list(pool.map(one, work))
        wall = time.perf_counter() - t0
        report["concurrency_statutes_k50"][clients] = {
            **_stats(ms), "qps": round(len(work) / wall, 1), "pg_rss_mb": pg_rss_mb()}
    report["pg_rss_idle_mb"] = rss_idle
    report["relation_mb"] = {r[0]: round(r[1] / 2**20, 2) for r in db.execute(text(
        "SELECT c.relname, pg_total_relation_size(c.oid) FROM pg_class c "
        "JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'assist' "
        "AND c.relkind = 'r' ORDER BY 2 DESC LIMIT 8"))}
    report["pg_settings"] = {k: db.execute(text(f"SHOW {k}")).scalar()
                             for k in ("shared_buffers", "work_mem", "max_connections")}

    # 7 — growth: exact scan over ×N replicated statute vectors (TEMP, scratch only)
    report["growth_exact_k50_ms"] = {}
    with create_engine(args.db).connect() as w:
        vt = store.vector_type(sessionmaker(bind=w)())
        op = f'OPERATOR("{store.vector_schema(sessionmaker(bind=w)())}".<=>)'
        for n in args.scale:
            w.execute(text("DROP TABLE IF EXISTS pg_temp.grow"))
            w.execute(text(f"CREATE TEMP TABLE grow AS SELECT e.embedding FROM "
                           f"assist.statute_chunk_embeddings e, generate_series(1, {n})"))
            size = w.execute(text("SELECT count(*) FROM grow")).scalar()
            ms = [_timed(lambda q=q: w.execute(text(
                f"SELECT 1 FROM grow ORDER BY embedding {op} CAST(:q AS {vt}) LIMIT 50"),
                {"q": _lit(qvec[q])}).all()) for q in questions[:30]]
            report["growth_exact_k50_ms"][size] = _stats(ms)
        w.rollback()
    print(json.dumps(report, indent=1))
    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
