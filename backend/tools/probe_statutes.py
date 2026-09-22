"""Domain C targeting probe — the statute lane, scored the way a reader experiences it.

Run it against a database that already holds the ingested statute corpus:

    python3 -m tools.probe_statutes                       # the shipped ranking
    python3 -m tools.probe_statutes --variants            # the ranking bake-off too

`tools/probe_targeting.py` scores the document lane: it ingests statute PDFs AS
DOCUMENTS and anchors each question to a `chunks` row. That measures `parse_pdf`, not
the corpus production actually answers a statute question from — `search_statutes` over
`statute_chunks`, built by a different chunker (`section-N`) from a different extractor.

THREE things are scored, separately, because they fail separately (2026-09-21):

* **evidence** — is the answering text among the hits? Anchor containment: the dataset's
  `anchor` is a verbatim span of the passage that answers the question, so a hit is a
  returned section whose text contains it. That needs no gold chunk id and survives a
  re-chunk, which is the point.
* **citation** — is that text returned under the Act and section a lawyer would cite?
  A right answer under a wrong citation scored as a clean hit until this existed: the
  IT Act's s. 70B(7) came back as `s. 266A(4) - Punishment for sending offensive
  messages`, and anchor containment cannot see it.
* **refusal grounding** — for a NOT_FOUND question, does the section that SHOWS the Act
  fixes no answer arrive? Retrieval returning nothing is not the goal; the gate refuses,
  and it must refuse from the right provision.

Nothing here calls a provider. Embeddings stay local, and `--lexical-only` drops even
those, so a difference between two runs is the retrieval mechanism and nothing else.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import statistics
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
os.environ.setdefault("LEGALMIND_SOURCE_MATERIAL_DIR", "/root/Legalmind.v1/legal-docs")

from sqlalchemy import create_engine
from sqlalchemy import text as sql_text
from sqlalchemy.orm import sessionmaker

from legalmind import config
from legalmind.assist import statutes
from legalmind.security import permissions as P

DATASET = pathlib.Path("tests/assist_eval/questions_draft.json")
# Domain C is authorized by `assist.ask` alone (AM-32 r8) — the statute corpus is public
# law, not an internal position, so `configuration.view` is not part of this gate.
PERMISSIONS = frozenset({P.ASSIST_ASK})

# Two named cases that must never regress, whatever the ranking does: an Act named in
# the question (AM-50 r3) and a section numbered in it (AM-47) each rank first.
NAMED_ACT = ("What is the DPDP Act?", "The Digital Personal Data Protection Act, 2023")
EXACT_SECTION = ("What does section 43A of the IT Act say about compensation?", "43A")


def _normalize(text: str) -> str:
    return " ".join((text or "").split()).lower()


def _cites(hit, expected: dict) -> bool:
    """Act and section only. The sub-section a hit carries depends on how the section
    was packed into chunks, which is not a citation error."""
    return (hit.official_title == expected["act"]
            and hit.section_number.upper() == expected["section"].upper())


def score(db, questions: list[dict], *, limit: int, embed, search=None) -> dict:
    search = search or (lambda q: statutes.search_statutes(
        db, query=q, permissions=PERMISSIONS, limit=limit, embed_query=embed))
    answerable = [q for q in questions if q["expected"] == "ANSWERABLE"]
    refusals = [q for q in questions if q["expected"] == "NOT_FOUND"]
    m: dict = {"n": len(answerable), "hit1": 0, "hit3": 0, "found": 0, "mrr": 0.0,
               "cited": 0, "cite_of": 0, "miscited": [], "grounded": 0, "wrong_act": 0,
               "n_refusal": len(refusals), "latency": [], "ranks": {}}
    for q in answerable:
        anchor = _normalize(q["anchor"])
        t0 = time.perf_counter()
        hits = search(q["question"])
        m["latency"].append((time.perf_counter() - t0) * 1000)
        ranks = [i for i, h in enumerate(hits, 1) if anchor in _normalize(h.content)]
        m["ranks"][q["id"]] = ranks[0] if ranks else None
        if not ranks:
            continue
        m["found"] += 1
        m["mrr"] += 1.0 / ranks[0]
        m["hit3"] += ranks[0] <= 3
        m["hit1"] += ranks[0] == 1
        expected = q.get("expected_citation")
        if not expected:
            continue
        m["cite_of"] += 1
        carrier = hits[ranks[0] - 1]
        if _cites(carrier, expected):
            m["cited"] += 1
        else:
            m["miscited"].append((q["id"], carrier.citation,
                                  f'{expected["act"]}, s. {expected["section"]}'))
    for q in refusals:
        hits = search(q["question"])
        expected = q.get("expected_citation")
        if expected and any(_cites(h, expected) for h in hits):
            m["grounded"] += 1
        if expected and hits and hits[0].official_title != expected["act"]:
            m["wrong_act"] += 1
    spot = {}
    for label, (question, want) in (("named-Act", NAMED_ACT),
                                    ("exact-section", EXACT_SECTION)):
        hits = search(question)
        spot[label] = bool(hits) and want in (hits[0].official_title,
                                              hits[0].section_number)
    m["spot"] = spot
    return m


def report(name: str, m: dict) -> None:
    n, r = max(m["n"], 1), max(m["n_refusal"], 1)
    cite = f'{m["cited"]}/{m["cite_of"]}' if m["cite_of"] else "n/a"
    lat = statistics.median(m["latency"]) if m["latency"] else 0.0
    print(f'{name:12} {m["hit1"]/n:6.3f} {m["hit3"]/n:6.3f} {m["found"]/n:7.3f} '
          f'{m["mrr"]/n:6.3f} {cite:>7} {m["grounded"]}/{r:<3} {m["wrong_act"]}/{r:<3} '
          f'{"Y" if m["spot"]["named-Act"] else "N":^6}{"Y" if m["spot"]["exact-section"] else "N":^6}'
          f'{lat:7.0f}')


def header(limit: int) -> None:
    print(f'{"variant":12} {"hit@1":>6} {"hit@3":>6} {"rec@" + str(limit):>7} {"MRR":>6} '
          f'{"cite":>7} {"ground":<4} {"wrongAct":<4} {"named":^6}{"exact":^6}{"p50ms":>7}')
    print("-" * 94)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.environ.get("LEGALMIND_DATABASE_URL"))
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--lexical-only", action="store_true",
                    help="skip the local embedder, so only the lexical path is scored")
    ap.add_argument("--variants", action="store_true",
                    help="also score the ranking alternatives (read-only, no config change)")
    args = ap.parse_args()
    if not args.database_url:
        print("FAIL  no database: pass --database-url or set LEGALMIND_DATABASE_URL")
        return 2

    questions = [q for q in json.loads(DATASET.read_text())["questions"]
                 if q.get("category") == "STATUTE"]
    db = sessionmaker(bind=create_engine(args.database_url, future=True), future=True)()
    if not statutes.available(db):
        print("SKIP  no statute corpus in this database; run tools.ingest_statutes")
        return 0

    embed = None
    if not args.lexical_only:
        from legalmind.assist import embedding_runtime
        embed = embedding_runtime.embed_query

    # The version the ROWS were written with, never the version this checkout would
    # write: the whole use of this probe is comparing two corpora, and reading the
    # constant would label both with whichever code happened to run it.
    versions = db.execute(sql_text(
        f'SELECT DISTINCT chunking_algorithm_version '
        f'FROM "{config.assist_schema()}".statute_chunks')).scalars().all()
    chunks, sections = db.execute(sql_text(
        f'SELECT count(*), count(DISTINCT (statute_id, section_number)) '
        f'FROM "{config.assist_schema()}".statute_chunks')).one()
    answerable = sum(q["expected"] == "ANSWERABLE" for q in questions)
    print(f"Domain C probe — {answerable} answerable + {len(questions) - answerable} "
          f"must-refuse STATUTE questions, {len(statutes.holdings(db))} Acts, "
          f"{chunks} chunks / {sections} sections, chunker "
          f"{'/'.join(sorted(versions)) or 'none'}")
    print(f"evidence = a returned section containing the question's verbatim anchor; "
          f"citation = that section's Act + number; limit={args.limit}"
          f"{'; lexical only' if args.lexical_only else ''}\n")
    header(args.limit)
    base = score(db, questions, limit=args.limit, embed=embed)
    report("current", base)
    if args.variants:
        from tools import statute_rank_variants as V
        for name in V.VARIANTS:
            m = score(db, questions, limit=args.limit, embed=embed,
                      search=V.searcher(db, name, limit=args.limit, embed=embed))
            report(name, m)
    print("\nper-question evidence rank (None = not in the returned hits):")
    for qid, rank in sorted(base["ranks"].items()):
        print(f"  {qid}  {rank}")
    if base["miscited"]:
        print(f'\nwrong citation on retrieved evidence ({len(base["miscited"])}):')
        for qid, got, want in base["miscited"]:
            print(f"  {qid}  got  {got}\n        want {want}")
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
