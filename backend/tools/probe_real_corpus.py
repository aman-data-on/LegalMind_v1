"""Real-document retrieval probe — Ask charter D10/D11/D18(b). Zero Gemini.

    python3 -m tools.probe_real_corpus --db <scratch url> [--corpus DIR] [--write-keys]

Ingests every PDF and DOCX in the private corpus (default
`/root/.legalmind/test-corpus/raw`, never in the repository) through the production
`ingest_document` → `index_document_version` path into a SCRATCH database, derives probes
mechanically, and scores `store.search_hybrid` — the production document search.

Probes are derived from EVIDENCE rows (the parser's output), not chunks, so a chunker
change is measured against the same probe set, and a hit is "a returned chunk contains
the anchor". Families, per document, capped at PROBES_PER_FAMILY each:

    section_number   the document states "17.2"; the query is "17.2"; the anchor is the
                     opening words of that clause
    exact_terms      a word 4-gram occurring in one evidence row only; query = anchor
    unanswerable     a 4-gram from another document with a word this one never uses;
                     any hit is a false admission

Nothing authored, nothing asserting a legal position (rule 21). Output carries document
ids, families, clause numbers, ranks and cause codes — never document text (D11). The
committed keys (`tests/assist_eval/real_corpus_keys.json`) hold SHA-256 hashes of each
probe, so the probe set is pinned without the text leaving the corpus.

Miss causes, first that applies:
    ANCHOR_SPLIT    the anchor is in no single chunk but spans two adjacent chunks
    ANCHOR_LOST     the anchor is in no chunk at all (trimmed or not indexed)
    GATE_CLOSED     the gold chunk is among the gated-out candidates
    RANK_CUTOFF     the gold chunk is in the 50-deep candidate pool, below rank 10
    RETRIEVAL_MISS  not in the pool
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import sys
import uuid
from collections import Counter, defaultdict
from itertools import pairwise

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
os.environ.setdefault("LEGALMIND_ASSIST_SCHEMA", "assist")
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from legalmind import config
from legalmind.assist import embedding_runtime, store
from legalmind.assist.indexing import index_document_version
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.ingestion.service import ingest_document
from legalmind.ingestion.storage import LocalFilesystemStorage
from legalmind.ingestion.validation import DOCX_MIME, PDF_MIME

CORPUS = pathlib.Path("/root/.legalmind/test-corpus/raw")
KEYS = pathlib.Path(__file__).resolve().parents[1] / "tests/assist_eval/real_corpus_keys.json"
MIME = {".pdf": PDF_MIME, ".docx": DOCX_MIME}
PROBES_PER_FAMILY = 12
NGRAM = 4
TOP_K = 10
POOL = 50
ANCHOR_WORDS = 8
# "17.2", "99.95" and "5,000" stay one word, as the documents and full-text search write
# them: split into "17 2", every numeric probe was a query no reader would type, and all
# 36 gate-closed misses of 2026-10-01 were exactly that (decision A-7).
_WORD = re.compile(r"[a-z0-9](?:[a-z0-9'-]|[.,](?=[0-9]))*")


def _words(s: str) -> list[str]:
    return _WORD.findall(s.lower())


def _contains(chunk: str, anchor: list[str]) -> bool:
    words, n = _words(chunk), len(anchor)
    return any(words[i:i + n] == anchor for i in range(len(words) - n + 1))


def _sha(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:16]


def ingest(db, corpus: pathlib.Path) -> dict[str, uuid.UUID]:
    owner = M.User(email=f"probe-{uuid.uuid4().hex[:8]}@example.test", name="probe",
                   status=E.UserStatus.ACTIVE)
    db.add(owner)
    db.flush()
    # D11: the documents' bytes stay inside the private corpus directory (mode 700) —
    # never a temp directory, which made uncontrolled copies (found 2026-10-03).
    storage = LocalFilesystemStorage(CORPUS.parent / "objects")
    versions = {}
    for path in sorted(corpus.iterdir()):
        if path.suffix not in MIME:
            continue
        contract = M.Contract(owner_id=owner.id, name=path.stem, contract_type="OTHER",
                              status=E.ContractStatus.ACTIVE)
        db.add(contract)
        db.flush()
        try:
            result = ingest_document(db, storage, contract_id=contract.id,
                                     uploaded_by=owner.id, data=path.read_bytes(),
                                     filename=path.name, declared_mime=MIME[path.suffix])
            index_document_version(db, result.document_version.id)
        except Exception as exc:          # a document that fails is reported, not hidden
            print(f"  NOT INGESTED {path.stem}: {type(exc).__name__}")
            continue
        versions[path.stem] = result.document_version.id
    db.commit()
    return versions


def _evidence(db, dv) -> list[tuple[str | None, str]]:
    return [(r[0], r[1]) for r in db.execute(text(
        "SELECT section_number, content FROM document_evidence WHERE document_version_id = :v "
        "ORDER BY start_offset NULLS LAST, id"), {"v": dv}).all()]


def _chunks(db, dv) -> list[tuple[uuid.UUID, str]]:
    return [(r[0], r[1]) for r in db.execute(text(
        f'SELECT id, content FROM "{config.assist_schema()}".chunks '
        "WHERE document_version_id = :v ORDER BY ordinal"), {"v": dv}).all()]


def derive(evidence_by_doc: dict[str, list]) -> list[dict]:
    # A probe's query is the document's own text for those words — "Rs. 5,000/-",
    # "party's", "(30)" exactly as written — because a reader copies a phrase; rebuilding
    # it from normalised words made queries no full-text parser would match (A-7).
    grams_by_doc, verbatim = {}, {}
    for doc, rows in evidence_by_doc.items():
        counts: Counter = Counter()
        for _, content in rows:
            spans = list(_WORD.finditer(content.lower()))
            grams = set()
            for i in range(len(spans) - NGRAM + 1):
                g = " ".join(m.group() for m in spans[i:i + NGRAM])
                grams.add(g)
                verbatim.setdefault(g, content[spans[i].start():spans[i + NGRAM - 1].end()])
            counts.update(grams)
        grams_by_doc[doc] = counts
    probes = []
    for doc, rows in sorted(evidence_by_doc.items()):
        sections = Counter(s for s, _ in rows if s and "." in s)
        picked = [(s, c) for s, c in rows if s and sections[s] == 1]
        for s, content in picked[:PROBES_PER_FAMILY]:
            anchor = _words(content)[:ANCHOR_WORDS]
            if len(anchor) >= 3:
                probes.append({"doc": doc, "family": "section_number", "query": s,
                               "anchor": anchor, "section": s})
        unique = sorted(g for g, n in grams_by_doc[doc].items()
                        if n == 1 and not all(len(x) < 4 for x in g.split()))
        for g in unique[:PROBES_PER_FAMILY]:
            probes.append({"doc": doc, "family": "exact_terms", "query": verbatim[g],
                           "anchor": g.split(), "section": None})
        vocab = {w for _, c in rows for w in _words(c)}
        foreign = sorted(g for other, counts in grams_by_doc.items() if other != doc
                         for g in counts if any(w not in vocab for w in g.split()))
        for g in foreign[:PROBES_PER_FAMILY]:
            probes.append({"doc": doc, "family": "unanswerable", "query": verbatim[g],
                           "anchor": [], "section": None})
    for p in probes:
        p["key"] = _sha(p["doc"], p["family"], p["query"], " ".join(p["anchor"]))
    return probes


def _cause(chunks, anchor, ranked_all, gate_open, gold):
    if not gold:
        split = any(_contains(a[1] + " " + b[1], anchor) for a, b in pairwise(chunks))
        return "ANCHOR_SPLIT" if split else "ANCHOR_LOST"
    if not gate_open and gold & set(ranked_all[:TOP_K]):
        return "GATE_CLOSED"
    return "RANK_CUTOFF" if gold & set(ranked_all) else "RETRIEVAL_MISS"


def _gold(chunks, anchor) -> set:
    """Chunks that answer the probe: those holding the anchor, and — when that chunk is
    only a heading ("17.2 Fees") — the chunks after it up to the first that is not, since
    a reader asking for 17.2 wants the clause, not its title (2026-09-30: 61 of 61
    clause-number "misses" were heading chunks, 51 answered by the clause body)."""
    out = set()
    for i, (cid, content) in enumerate(chunks):
        if _contains(content, anchor):
            out.add(cid)
            j = i
            while store.is_fragment(chunks[j][1]) and j + 1 < len(chunks):
                j += 1
                out.add(chunks[j][0])
    return out


def score(db, versions, probes) -> dict:
    fam = defaultdict(lambda: {"n": 0, "hit10": 0, "hit1": 0, "mrr": 0.0, "false_admit": 0})
    misses = []
    # Phase 2 A3: near-duplicate files make the same unanswerable probe twice (384
    # scored, 163 distinct). Counted both ways; the as-scored column stays comparable.
    unanswerable: dict[str, bool] = {}
    chunk_cache = {doc: _chunks(db, dv) for doc, dv in versions.items()}
    for p in probes:
        dv, chunks = versions[p["doc"]], chunk_cache[p["doc"]]
        out = store.search_hybrid(db, document_version_id=dv, query=p["query"],
                                  embed_query=embedding_runtime.embed_query)
        pool = store.search_hybrid(db, document_version_id=dv, query=p["query"],
                                   embed_query=embedding_runtime.embed_query, limit=POOL,
                                   candidates=True)
        f = fam[p["family"]]
        f["n"] += 1
        ranked = [h.chunk_id for h in out.hits][:TOP_K]
        if p["family"] == "unanswerable":
            f["false_admit"] += bool(ranked)
            unanswerable[p["key"]] = unanswerable.get(p["key"], False) or bool(ranked)
            continue
        gold = _gold(chunks, p["anchor"])
        rank = next((i for i, cid in enumerate(ranked, 1) if cid in gold), None)
        if rank:
            f["hit10"] += 1
            f["mrr"] += 1 / rank
            f["hit1"] += rank == 1
        else:
            misses.append({"doc": p["doc"], "family": p["family"], "section": p["section"],
                           "key": p["key"], "cause": _cause(
                               chunks, p["anchor"], [h.chunk_id for h in pool.hits],
                               out.gate_open, gold)})
    return {"families": dict(fam), "misses": misses, "distinct": unanswerable}


def report(result: dict) -> dict:
    fams = result["families"]
    ans = [f for k, f in fams.items() if k != "unanswerable"]
    n = sum(f["n"] for f in ans) or 1
    un = fams.get("unanswerable", {"n": 0, "false_admit": 0})
    summary = {"answerable": n, "recall@10": round(sum(f["hit10"] for f in ans) / n, 4),
               "hit@1": round(sum(f["hit1"] for f in ans) / n, 4),
               "mrr": round(sum(f["mrr"] for f in ans) / n, 4),
               "unanswerable": un["n"],
               "false_admission": round(un["false_admit"] / (un["n"] or 1), 4),
               "unanswerable_distinct": len(result.get("distinct", {})),
               "false_admission_distinct": round(
                   sum(result.get("distinct", {}).values())
                   / (len(result.get("distinct", {})) or 1), 4),
               "wrong_source": "n/a — document search is scoped to one version in SQL",
               "miss_causes": dict(Counter(m["cause"] for m in result["misses"]))}
    for k, f in sorted(fams.items()):
        m = f["n"] or 1
        summary[f"family:{k}"] = {"n": f["n"], "recall@10": round(f["hit10"] / m, 4),
                                  "hit@1": round(f["hit1"] / m, 4),
                                  "mrr": round(f["mrr"] / m, 4),
                                  "false_admission": f["false_admit"]}
    return summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True, help="a SCRATCH database url; never live")
    ap.add_argument("--corpus", default=str(CORPUS))
    ap.add_argument("--json", default=None, help="write summary + misses (no text) here")
    ap.add_argument("--write-keys", action="store_true")
    ap.add_argument("--reuse", action="store_true",
                    help="score the corpus already ingested in --db instead of re-ingesting")
    args = ap.parse_args(argv)
    from alembic.config import Config

    from alembic import command
    cfg = Config(str(pathlib.Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", args.db)
    command.upgrade(cfg, "head")
    db = sessionmaker(bind=create_engine(args.db, future=True), future=True)()
    versions = ({r[0].rsplit(".", 1)[0]: r[1] for r in db.execute(text(
                    "SELECT original_filename, id FROM document_versions")).all()}
                if args.reuse else ingest(db, pathlib.Path(args.corpus)))
    probes = derive({d: _evidence(db, v) for d, v in versions.items()})
    if args.write_keys:
        KEYS.write_text(json.dumps({"probes": sorted(p["key"] for p in probes)}, indent=1))
        print(f"wrote {len(probes)} probe keys")
    elif KEYS.exists():
        pinned = set(json.loads(KEYS.read_text())["probes"])
        drift = len({p["key"] for p in probes} ^ pinned)
        probes = [p for p in probes if p["key"] in pinned]
        print(f"keys: {len(probes)} pinned probes scored, {drift} differ from the corpus")
    result = score(db, versions, probes)
    summary = report(result)
    print(json.dumps(summary, indent=1))
    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(
            {"summary": summary, "misses": result["misses"],
             "documents": len(versions)}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
