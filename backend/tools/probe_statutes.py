"""Domain C targeting probe — the statute lane, scored the way a reader experiences it.

Run it against a database that already holds the ingested statute corpus:

    python3 -m tools.probe_statutes

`tools/probe_targeting.py` scores the document lane: it ingests statute PDFs AS
DOCUMENTS and anchors each question to a `chunks` row. That measures `parse_pdf`, not
the corpus production actually answers a statute question from — `search_statutes` over
`statute_chunks`, built by a different chunker (`section-N`) from a different extractor.
Until this file existed, the lane serving every GENERAL LAW question had no eval at all.

Scoring is anchor containment: the dataset's `anchor` is a verbatim span of the passage
that answers the question, so a hit is a returned section whose text contains it. That
needs no gold chunk id and survives a re-chunk, which is the point — the ids change
every time the chunker does.

Nothing here calls a provider. Embeddings stay local, and `--lexical-only` drops even
those, so a difference between two runs is the retrieval mechanism and nothing else.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
os.environ.setdefault("LEGALMIND_SOURCE_MATERIAL_DIR", "/root/Legalmind.v1/legal-docs")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from legalmind import config
from legalmind.assist import statutes
from legalmind.security import permissions as P

DATASET = pathlib.Path("tests/assist_eval/questions_draft.json")
# Domain C is authorized by `assist.ask` alone (AM-32 r8) — the statute corpus is public
# law, not an internal position, so `configuration.view` is not part of this gate.
PERMISSIONS = frozenset({P.ASSIST_ASK})


def _normalize(text: str) -> str:
    return " ".join(text.split()).lower()


def score(db, questions: list[dict], *, limit: int, embed) -> dict:
    hits1 = hits3 = found = n = 0
    mrr = 0.0
    misses: list[tuple[str, str]] = []
    for q in questions:
        anchor = _normalize(q["anchor"])
        hits = statutes.search_statutes(db, query=q["question"],
                                        permissions=PERMISSIONS, limit=limit,
                                        embed_query=embed)
        n += 1
        ranks = [i for i, h in enumerate(hits, 1) if anchor in _normalize(h.content)]
        if not ranks:
            misses.append((q["id"], hits[0].citation if hits else "nothing returned"))
            continue
        found += 1
        mrr += 1.0 / ranks[0]
        hits3 += ranks[0] <= 3
        hits1 += ranks[0] == 1
    return {"n": n, "hit@1": hits1 / n, "hit@3": hits3 / n, f"recall@{limit}": found / n,
            "mrr": mrr / n, "misses": misses}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.environ.get("LEGALMIND_DATABASE_URL"))
    ap.add_argument("--limit", type=int, default=6)
    ap.add_argument("--lexical-only", action="store_true",
                    help="skip the local embedder, so only the lexical path is scored")
    args = ap.parse_args()
    if not args.database_url:
        print("FAIL  no database: pass --database-url or set LEGALMIND_DATABASE_URL")
        return 2

    questions = [q for q in json.loads(DATASET.read_text())["questions"]
                 if q.get("category") == "STATUTE" and q["expected"] == "ANSWERABLE"]
    db = sessionmaker(bind=create_engine(args.database_url, future=True), future=True)()
    if not statutes.available(db):
        print("SKIP  no statute corpus in this database; run tools.ingest_statutes")
        return 0

    embed = None
    if not args.lexical_only:
        from legalmind.assist import embedding_runtime
        embed = embedding_runtime.embed_query

    holdings = statutes.holdings(db)
    # The version the ROWS were written with, never the version this checkout would
    # write: the whole use of this probe is comparing two corpora, and reading the
    # constant would label both with whichever code happened to run it.
    from sqlalchemy import text as sql_text
    versions = db.execute(sql_text(
        f'SELECT DISTINCT chunking_algorithm_version '
        f'FROM "{config.assist_schema()}".statute_chunks')).scalars().all()
    print(f"Domain C probe — {len(questions)} answerable STATUTE questions, "
          f"{len(holdings)} Acts, chunker {'/'.join(sorted(versions)) or 'none'}")
    print(f"scoring: a hit is a returned section containing the question's verbatim "
          f"anchor; limit={args.limit}"
          f"{'; lexical only' if args.lexical_only else ''}\n")
    m = score(db, questions, limit=args.limit, embed=embed)
    print(f"  n={m['n']}  hit@1={m['hit@1']:.3f}  hit@3={m['hit@3']:.3f}  "
          f"recall@{args.limit}={m[f'recall@{args.limit}']:.3f}  mrr={m['mrr']:.3f}")
    if m["misses"]:
        print(f"\n  not retrieved ({len(m['misses'])}):")
        for qid, top in m["misses"]:
            print(f"    {qid}  top result: {top}")
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
